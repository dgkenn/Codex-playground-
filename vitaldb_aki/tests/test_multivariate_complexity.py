"""test_multivariate_complexity.py -- Offline unit tests for the multivariate
SYSTEM-WIDE physiologic-complexity feature family (§7C/§7F novel).

All tests are pure-math / in-memory; no network access, no VitalDB downloads.
The PURE helpers are tested against hand-built synthetic ensembles with KNOWN
expected direction:
  * a RIGID / perfectly-coupled ensemble => LOW joint sample entropy + HIGH
    pairwise correlation;
  * a COMPLEX / decoupled (independent) ensemble => HIGHER joint sample entropy
    + LOW pairwise correlation.

Run with:
    python3 -m unittest vitaldb_aki.tests.test_multivariate_complexity -v
"""
from __future__ import annotations

import math
import os
import sys
import unittest
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from vitaldb_aki.features.multivariate_complexity import (
    # Module-level constants
    SPECS,
    CORE_SIGNALS,
    MIN_CORE_SIGNALS,
    MIN_JOINT_POINTS,
    ALIGN_DT_S,
    ALIGN_MAX_STALE_S,
    # Pure helpers
    _align_grid,
    _zscore,
    _pearson,
    _pairwise_corr_stats,
    _multivariate_sampen,
    _uniform_cap_channels,
    # Case-level + entry point
    compute_multivariate_complexity,
    extract,
)
from vitaldb_aki.features.base import audit_specs


def _lcg(seed: int):
    """Deterministic pseudo-random generator (no numpy / no random import in core).

    Linear congruential generator returning floats in [0, 1); used to build
    'independent noisy' synthetic channels reproducibly.
    """
    state = {"s": seed & 0xFFFFFFFF}

    def _next() -> float:
        state["s"] = (1103515245 * state["s"] + 12345) & 0x7FFFFFFF
        return state["s"] / float(0x7FFFFFFF)

    return _next


def _structured_noisy(seed: int, n: int, smooth: float = 0.6) -> list[float]:
    """A noisy-but-CONTINUOUS channel: an exponentially-smoothed random walk."""
    rng = _lcg(seed)
    out: list[float] = []
    x = 0.0
    for _ in range(n):
        x = smooth * x + (1.0 - smooth) * (rng() - 0.5)
        out.append(x)
    return out


def _driver(n: int) -> list[float]:
    """A smooth shared physiologic driver (e.g. respiratory / autonomic rhythm)."""
    return [math.sin(i * 0.13) for i in range(n)]


def _loosely_coupled(seed: int, n: int, noise: float = 0.5) -> list[float]:
    """A loosely-coupled channel: shared smooth driver + independent noise.

    A REALISTIC complex/decoupled ensemble channel. Multivariate SampEn across
    several *fully independent* channels is, by construction, almost always
    undefined at r=0.2 (the composite delay vector must match in EVERY channel
    at once, which essentially never happens for the extended template -> a_cnt=0
    -> None). Real physiologic signals are not independent: they share common
    drivers (respiration, autonomic tone). We model that with a smooth shared
    driver plus per-channel noise, giving a complex-yet-DEFINED ensemble whose
    joint entropy is genuinely HIGHER than a rigid one. (noise>~0.5 decouples the
    channels enough that the joint statistic again becomes undefined -- a real,
    documented property of N-way SampEn.)
    """
    drv = _driver(n)
    nz = _structured_noisy(seed, n, smooth=0.6)
    return [(1.0 - noise) * drv[i] + noise * nz[i] for i in range(n)]


# ===========================================================================
# 1. Module-level spec invariants (mirror test_pfds)
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
            self.assertEqual(s.timing, "intraop",
                             msg=f"{s.name} timing={s.timing!r}")

    def test_first_spec_is_available(self):
        self.assertEqual(SPECS[0].name, "mvcplx_available",
                         "First spec MUST be mvcplx_available")

    def test_no_duplicate_names(self):
        names = [s.name for s in SPECS]
        self.assertEqual(len(names), len(set(names)),
                         "Duplicate feature names in SPECS")

    def test_required_features_present(self):
        names = {s.name for s in SPECS}
        required = {
            "mvcplx_available",
            "mvcplx_n_signals",
            "mvcplx_joint_sampen",
            "mvcplx_mean_pairwise_corr",
            "mvcplx_corr_dispersion",
            "mvcplx_max_pairwise_corr",
        }
        missing = required - names
        self.assertFalse(missing, f"Missing specs: {missing}")

    def test_spec_count(self):
        self.assertEqual(len(SPECS), 6, "Expected exactly 6 feature specs")

    def test_core_signals(self):
        self.assertEqual(set(CORE_SIGNALS), {"MAP", "HR", "EtCO2", "SpO2"})


# ===========================================================================
# 2. _align_grid -- multi-signal joint alignment
# ===========================================================================

class TestAlignGrid(unittest.TestCase):
    def _ramp(self, start_v: float, step_v: float, n: int, dt: float = 5.0,
              t0: float = 0.0) -> list[tuple[float, float]]:
        return [(t0 + i * dt, start_v + i * step_v) for i in range(n)]

    def test_perfectly_aligned_signals(self):
        """Two signals sampled exactly on the grid => every point jointly valid."""
        n = 20
        a = self._ramp(50.0, 1.0, n, dt=5.0)
        b = self._ramp(80.0, -0.5, n, dt=5.0)
        names, channels = _align_grid({"A": a, "B": b}, 0.0, 95.0, dt=5.0)
        self.assertEqual(names, ["A", "B"])
        self.assertEqual(len(channels), 2)
        # 0..95 step 5 => 20 grid points, all jointly valid
        self.assertEqual(len(channels[0]), 20)
        self.assertEqual(len(channels[1]), 20)
        self.assertEqual(len(channels[0]), len(channels[1]))

    def test_empty_signal_voids_all_points(self):
        """An empty signal is never fresh => no jointly-valid points."""
        a = self._ramp(50.0, 1.0, 20, dt=5.0)
        names, channels = _align_grid({"A": a, "B": []}, 0.0, 95.0, dt=5.0)
        self.assertEqual(names, ["A", "B"])
        self.assertEqual(channels[0], [])
        self.assertEqual(channels[1], [])

    def test_no_signals(self):
        names, channels = _align_grid({}, 0.0, 95.0)
        self.assertEqual(names, [])
        self.assertEqual(channels, [])

    def test_invalid_window(self):
        a = self._ramp(50.0, 1.0, 20)
        names, channels = _align_grid({"A": a}, 100.0, 0.0)
        self.assertEqual(channels, [])

    def test_staleness_excludes_points(self):
        """A signal with a long gap is stale across the gap => those joint points drop."""
        # A is dense on the grid; B has a hole between t=20 and t=70 (>max_stale=10).
        a = [(i * 5.0, 50.0 + i) for i in range(20)]    # 0..95
        b = [(0.0, 80.0), (5.0, 80.0), (10.0, 80.0), (15.0, 80.0), (20.0, 80.0),
             (70.0, 81.0), (75.0, 81.0), (80.0, 81.0), (85.0, 81.0), (90.0, 81.0),
             (95.0, 81.0)]
        names, channels = _align_grid({"A": a, "B": b}, 0.0, 95.0,
                                      dt=5.0, max_stale=10.0)
        # B fresh: its t=20 sample stays fresh through g=25 (age 5) and g=30
        # (age 10, == max_stale), then goes stale at g=35..65 (the hole), and is
        # fresh again from g=70. So: 0,5,10,15,20,25,30 (7) + 70,75,80,85,90,95
        # (6) = 13. A point is dropped only once B exceeds max_stale.
        self.assertEqual(len(channels[0]), 13)
        self.assertEqual(len(channels[1]), 13)
        # And the points spanning the hole (35..65) are excluded.
        self.assertEqual(len(channels[0]), len(channels[1]))

    def test_never_exceeds_t_end(self):
        """No grid point is placed beyond t_end (leakage cutoff)."""
        a = [(i * 5.0, 50.0 + i) for i in range(40)]   # up to t=195
        # t_end at 50.0; B fresh throughout
        b = [(i * 5.0, 80.0) for i in range(40)]
        names, channels = _align_grid({"A": a, "B": b}, 0.0, 50.0, dt=5.0)
        # 0..50 step 5 => 11 points
        self.assertEqual(len(channels[0]), 11)

    def test_channels_parallel_and_equal_length(self):
        a = self._ramp(50.0, 1.0, 30)
        b = self._ramp(80.0, 0.0, 30)
        c = self._ramp(40.0, 0.2, 30)
        names, channels = _align_grid({"A": a, "B": b, "C": c}, 0.0, 145.0, dt=5.0)
        self.assertEqual(len(channels), 3)
        lengths = {len(ch) for ch in channels}
        self.assertEqual(len(lengths), 1, "All channels must be equal length")


# ===========================================================================
# 3. _zscore
# ===========================================================================

class TestZScore(unittest.TestCase):
    def test_zero_mean_unit_sd(self):
        z = _zscore([1.0, 2.0, 3.0, 4.0, 5.0])
        self.assertIsNotNone(z)
        self.assertAlmostEqual(sum(z) / len(z), 0.0, places=9)
        var = sum(x * x for x in z) / len(z)
        self.assertAlmostEqual(var, 1.0, places=9)

    def test_constant_returns_none(self):
        """Constant series has SD 0 => z-score undefined => None."""
        self.assertIsNone(_zscore([7.0] * 10))

    def test_too_short(self):
        self.assertIsNone(_zscore([1.0]))
        self.assertIsNone(_zscore([]))


# ===========================================================================
# 4. _pearson
# ===========================================================================

class TestPearson(unittest.TestCase):
    def test_perfect_positive(self):
        xs = [1.0, 2.0, 3.0, 4.0]
        ys = [2.0, 4.0, 6.0, 8.0]
        self.assertAlmostEqual(_pearson(xs, ys), 1.0, places=9)

    def test_perfect_negative(self):
        xs = [1.0, 2.0, 3.0, 4.0]
        ys = [8.0, 6.0, 4.0, 2.0]
        self.assertAlmostEqual(_pearson(xs, ys), -1.0, places=9)

    def test_constant_returns_none(self):
        xs = [1.0, 2.0, 3.0, 4.0]
        ys = [5.0, 5.0, 5.0, 5.0]
        self.assertIsNone(_pearson(xs, ys))

    def test_length_mismatch_or_short(self):
        self.assertIsNone(_pearson([1.0, 2.0], [1.0]))
        self.assertIsNone(_pearson([1.0], [1.0]))


# ===========================================================================
# 5. _pairwise_corr_stats
# ===========================================================================

class TestPairwiseCorrStats(unittest.TestCase):
    def test_rigid_ensemble_high_mean_corr(self):
        """Identical (coupled) channels => mean |r| ~ 1, dispersion ~ 0."""
        base = [float(i % 7) + 0.3 * i for i in range(40)]
        channels = [list(base), [2.0 * x + 1.0 for x in base], [-x for x in base]]
        mean_r, sd_r, max_r = _pairwise_corr_stats(channels)
        self.assertIsNotNone(mean_r)
        self.assertGreater(mean_r, 0.99, "Affine-coupled channels => |r| ~ 1")
        self.assertLess(sd_r, 1e-6)
        self.assertAlmostEqual(max_r, 1.0, places=6)

    def test_decoupled_ensemble_low_mean_corr(self):
        """Independent noisy channels => mean |r| well below 1."""
        r0 = _lcg(1)
        r1 = _lcg(98765)
        r2 = _lcg(424242)
        n = 200
        channels = [
            [r0() for _ in range(n)],
            [r1() for _ in range(n)],
            [r2() for _ in range(n)],
        ]
        mean_r, sd_r, max_r = _pairwise_corr_stats(channels)
        self.assertIsNotNone(mean_r)
        self.assertLess(mean_r, 0.3,
                        "Independent channels => low mean pairwise |corr|")

    def test_rigid_higher_than_decoupled(self):
        base = [math.sin(i * 0.3) for i in range(80)]
        rigid = [list(base), [1.5 * x for x in base], [0.7 * x - 2.0 for x in base]]
        r0, r1, r2 = _lcg(5), _lcg(55), _lcg(555)
        decoupled = [[r0() for _ in range(80)],
                     [r1() for _ in range(80)],
                     [r2() for _ in range(80)]]
        rigid_mean, _, _ = _pairwise_corr_stats(rigid)
        decoup_mean, _, _ = _pairwise_corr_stats(decoupled)
        self.assertGreater(rigid_mean, decoup_mean,
                           "Rigid ensemble must show higher mean |corr| than decoupled")

    def test_single_pair_sd_zero(self):
        a = [float(i) for i in range(10)]
        b = [2.0 * i for i in range(10)]
        mean_r, sd_r, max_r = _pairwise_corr_stats([a, b])
        self.assertAlmostEqual(sd_r, 0.0, places=9)

    def test_too_few_channels(self):
        self.assertEqual(_pairwise_corr_stats([[1.0, 2.0, 3.0]]), (None, None, None))

    def test_all_constant_channels_none(self):
        channels = [[5.0] * 10, [3.0] * 10]
        self.assertEqual(_pairwise_corr_stats(channels), (None, None, None))


# ===========================================================================
# 6. _multivariate_sampen -- the subtle one
# ===========================================================================

class TestMultivariateSampEn(unittest.TestCase):
    def _z(self, series: list[float]) -> list[float]:
        z = _zscore(series)
        assert z is not None
        return z

    def test_rigid_lower_than_complex(self):
        """KEY TEST: identical/coupled rigid channels => LOWER joint entropy than
        independent noisy channels."""
        n = 120
        # Rigid ensemble: three copies of one smooth deterministic signal (after
        # z-scoring they become identical => one effective dimension).
        base = [math.sin(i * 0.15) for i in range(n)]
        rigid = [self._z(base), self._z([1.3 * x for x in base]),
                 self._z([0.8 * x - 1.0 for x in base])]

        # Complex ensemble: three loosely-coupled channels (shared driver +
        # independent noise) -- a realistic decoupled-yet-defined ensemble.
        complex_ch = [
            self._z(_loosely_coupled(11, n)),
            self._z(_loosely_coupled(2222, n)),
            self._z(_loosely_coupled(333333, n)),
        ]

        se_rigid = _multivariate_sampen(rigid)
        se_complex = _multivariate_sampen(complex_ch)
        self.assertIsNotNone(se_rigid)
        self.assertIsNotNone(se_complex)
        self.assertLess(se_rigid, se_complex,
                        "Rigid/coupled ensemble must give LOWER joint sample "
                        "entropy than a decoupled noisy ensemble")

    def test_identical_channels_near_zero(self):
        """Perfectly identical (after z-score) channels => very low MVSampEn."""
        n = 100
        base = self._z([math.sin(i * 0.2) for i in range(n)])
        se = _multivariate_sampen([list(base), list(base), list(base)])
        self.assertIsNotNone(se)
        # A perfectly self-similar smooth signal has near-minimal entropy.
        self.assertLess(se, 0.6)

    def test_single_channel_matches_univariate_direction(self):
        """A single smooth channel should give lower entropy than a noisy one."""
        n = 120
        smooth = self._z([math.sin(i * 0.1) for i in range(n)])
        noisy = self._z(_structured_noisy(7, n))
        se_smooth = _multivariate_sampen([smooth])
        se_noisy = _multivariate_sampen([noisy])
        self.assertIsNotNone(se_smooth)
        self.assertIsNotNone(se_noisy)
        self.assertLess(se_smooth, se_noisy)

    def test_too_short_returns_none(self):
        self.assertIsNone(_multivariate_sampen([[0.0, 1.0, 0.0]], m=2))

    def test_no_channels_returns_none(self):
        self.assertIsNone(_multivariate_sampen([]))

    def test_unequal_length_returns_none(self):
        self.assertIsNone(_multivariate_sampen([[0.0, 1.0, 2.0, 3.0], [0.0, 1.0]]))

    def test_vectorized_matches_pure_python(self):
        """The numpy-vectorized MVSampEn is bit-equivalent to a reference triple-
        loop pure-Python implementation (exact, no cap)."""
        n = 200
        ch = [self._z(_loosely_coupled(s, n)) for s in (11, 222, 3333)]

        def _ref(channels, m=2, r=0.2):
            p = len(channels)
            nn = len(channels[0])

            def mf(mm):
                last = nn - mm + 1
                cnt = 0
                for i in range(last):
                    for j in range(i + 1, last):
                        ok = True
                        for c in channels:
                            for k in range(mm):
                                if abs(c[i + k] - c[j + k]) > r:
                                    ok = False
                                    break
                            if not ok:
                                break
                        if ok:
                            cnt += 1
                return cnt, last * (last - 1) // 2

            bc, bt = mf(m)
            ac, at = mf(m + 1)
            if bt == 0 or at == 0 or bc == 0 or ac == 0:
                return None
            return -math.log((ac / at) / (bc / bt))

        ref = _ref(ch)
        got = _multivariate_sampen(ch)
        self.assertIsNotNone(ref)
        self.assertIsNotNone(got)
        self.assertAlmostEqual(got, ref, places=12,
                               msg="Vectorized MVSampEn must equal pure-Python reference")


# ===========================================================================
# 6b. POISON-PILL regression: a degenerate / rigid ensemble must return fast
#     with a sensible value (0.0 or None) and never hang.
# ===========================================================================

class TestMVSampEnDegenerateGuards(unittest.TestCase):
    def test_constant_channels_all_match_returns_zero(self):
        """Channels with ~0 joint spread (every composite pair within r) => the
        all-match short-circuit returns 0.0 (maximal rigidity), fast."""
        import time
        # Three near-flat channels (spread << r) -> every base-length pair matches.
        chans = [[float(c) + 0.0001 * (i % 2) for i in range(1500)]
                 for c in (0, 0, 0)]
        t0 = time.perf_counter()
        result = _multivariate_sampen(chans, m=2, r=0.2)
        dt = time.perf_counter() - t0
        self.assertEqual(result, 0.0,
                         "Rigid/constant ensemble => MVSampEn 0.0")
        self.assertLess(dt, 0.5, "All-match short-circuit must avoid the second matrix")

    def test_non_finite_returns_none(self):
        chans = [[1.0, 2.0, float("nan"), 4.0, 5.0],
                 [1.0, 2.0, 3.0, 4.0, 5.0]]
        self.assertIsNone(_multivariate_sampen(chans, m=2, r=0.2))

    def test_short_returns_none(self):
        self.assertIsNone(_multivariate_sampen([[0.0, 1.0, 0.0], [0.0, 1.0, 0.0]],
                                               m=2))


# ===========================================================================
# 7. _uniform_cap_channels
# ===========================================================================

class TestUniformCapChannels(unittest.TestCase):
    def test_caps_in_lockstep(self):
        n = 5000
        channels = [[float(i) for i in range(n)], [float(2 * i) for i in range(n)]]
        capped = _uniform_cap_channels(channels, maxlen=2000)
        self.assertLessEqual(len(capped[0]), 2000)
        self.assertEqual(len(capped[0]), len(capped[1]),
                         "Both channels must be capped in lockstep")

    def test_short_unchanged(self):
        channels = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]
        capped = _uniform_cap_channels(channels, maxlen=2000)
        self.assertEqual(capped, channels)

    def test_empty(self):
        self.assertEqual(_uniform_cap_channels([]), [])
        self.assertEqual(_uniform_cap_channels([[]]), [[]])


# ===========================================================================
# 8. compute_multivariate_complexity -- gate + integration
# ===========================================================================

class TestComputeMultivariateComplexity(unittest.TestCase):
    def _signal(self, value_fn, n: int, dt: float = 5.0,
                t0: float = 0.0) -> list[tuple[float, float]]:
        return [(t0 + i * dt, value_fn(i)) for i in range(n)]

    def test_missing_returns_available_zero_others_none(self):
        """Empty ensemble => mvcplx_available=0, all others None."""
        row = compute_multivariate_complexity({}, 0.0, 100.0)
        self.assertEqual(row["mvcplx_available"], 0)
        for s in SPECS:
            if s.name != "mvcplx_available":
                self.assertIsNone(row[s.name], f"{s.name} should be None")

    def test_too_few_core_signals(self):
        """Only 2 core signals present => below MIN_CORE_SIGNALS => unavailable."""
        n = 80
        sigs = {
            "MAP": self._signal(lambda i: 80.0 + math.sin(i * 0.2), n),
            "HR": self._signal(lambda i: 70.0 + math.cos(i * 0.2), n),
        }
        row = compute_multivariate_complexity(sigs, 0.0, (n - 1) * 5.0)
        self.assertEqual(row["mvcplx_available"], 0)
        self.assertIsNone(row["mvcplx_joint_sampen"])

    def test_too_few_joint_points(self):
        """3 core signals but < MIN_JOINT_POINTS aligned points => unavailable."""
        n = 20  # only 20 grid points < 50
        sigs = {
            "MAP": self._signal(lambda i: 80.0 + math.sin(i * 0.2), n),
            "HR": self._signal(lambda i: 70.0 + math.cos(i * 0.2), n),
            "EtCO2": self._signal(lambda i: 35.0 + 0.1 * (i % 5), n),
        }
        row = compute_multivariate_complexity(sigs, 0.0, (n - 1) * 5.0)
        self.assertEqual(row["mvcplx_available"], 0)

    def test_available_with_three_core_signals(self):
        """3 core signals + enough joint points => available with full row."""
        n = 120
        sigs = {
            "MAP": self._signal(lambda i: 80.0 + 5.0 * math.sin(i * 0.15), n),
            "HR": self._signal(lambda i: 70.0 + 4.0 * math.cos(i * 0.11), n),
            "EtCO2": self._signal(lambda i: 35.0 + 2.0 * math.sin(i * 0.07), n),
        }
        t_end = (n - 1) * 5.0
        row = compute_multivariate_complexity(sigs, 0.0, t_end)
        self.assertEqual(row["mvcplx_available"], 1)
        self.assertEqual(row["mvcplx_n_signals"], 3)
        self.assertIsNotNone(row["mvcplx_joint_sampen"])
        self.assertIsNotNone(row["mvcplx_mean_pairwise_corr"])
        self.assertIsNotNone(row["mvcplx_corr_dispersion"])
        self.assertIsNotNone(row["mvcplx_max_pairwise_corr"])
        self.assertGreaterEqual(row["mvcplx_mean_pairwise_corr"], 0.0)
        self.assertLessEqual(row["mvcplx_max_pairwise_corr"], 1.0)

    def test_rigid_ensemble_lower_joint_sampen_than_complex_full_pipeline(self):
        """End-to-end: rigid coupled ensemble has lower joint SampEn AND higher
        mean pairwise corr than a decoupled one, through the case-level path."""
        n = 140
        t_end = (n - 1) * 5.0
        # Rigid: all 3 core signals are affine functions of one smooth driver.
        drive = [math.sin(i * 0.13) for i in range(n)]
        rigid_sigs = {
            "MAP": [(i * 5.0, 80.0 + 6.0 * drive[i]) for i in range(n)],
            "HR": [(i * 5.0, 70.0 + 9.0 * drive[i]) for i in range(n)],
            "EtCO2": [(i * 5.0, 35.0 + 3.0 * drive[i]) for i in range(n)],
        }
        # Complex: 3 loosely-coupled core signals (shared driver + own noise).
        c0 = _loosely_coupled(101, n)
        c1 = _loosely_coupled(202, n)
        c2 = _loosely_coupled(303, n)
        complex_sigs = {
            "MAP": [(i * 5.0, 80.0 + 6.0 * c0[i]) for i in range(n)],
            "HR": [(i * 5.0, 70.0 + 9.0 * c1[i]) for i in range(n)],
            "EtCO2": [(i * 5.0, 35.0 + 3.0 * c2[i]) for i in range(n)],
        }
        rigid = compute_multivariate_complexity(rigid_sigs, 0.0, t_end)
        cplx = compute_multivariate_complexity(complex_sigs, 0.0, t_end)

        self.assertEqual(rigid["mvcplx_available"], 1)
        self.assertEqual(cplx["mvcplx_available"], 1)
        self.assertLess(rigid["mvcplx_joint_sampen"], cplx["mvcplx_joint_sampen"],
                        "Rigid ensemble must have LOWER joint sample entropy")
        self.assertGreater(rigid["mvcplx_mean_pairwise_corr"],
                           cplx["mvcplx_mean_pairwise_corr"],
                           "Rigid ensemble must have HIGHER mean pairwise |corr|")


# ===========================================================================
# 9. Leakage guard: no t > opend allowed
# ===========================================================================

class TestNoLeakage(unittest.TestCase):
    def test_grid_respects_cutoff(self):
        """Samples beyond t_end must not enter the aligned grid."""
        opend = 200.0
        # Both signals extend well past opend; values diverge AFTER opend.
        a = [(i * 5.0, 50.0) for i in range(80)]          # up to t=395
        b = [(i * 5.0, 80.0 if i * 5.0 <= opend else 999.0) for i in range(80)]
        from vitaldb_aki.features.multivariate_complexity import _clip_to_window
        a_clip = _clip_to_window(a, 0.0, opend)
        b_clip = _clip_to_window(b, 0.0, opend)
        names, channels = _align_grid({"A": a_clip, "B": b_clip}, 0.0, opend, dt=5.0)
        # No grid point beyond opend, so no 999.0 ever appears.
        for ch in channels:
            for v in ch:
                self.assertLess(v, 998.0, "Post-opend value leaked into grid")


# ===========================================================================
# 10. extract() smoke test (no network)
# ===========================================================================

class TestExtractSmokeTest(unittest.TestCase):
    """Smoke test extract() with synthetic cfg/cases/tracks (no network).

    extract() lazy-imports first_available from vitaldb_aki.data.tracks, so we
    patch at the source module.
    """

    def test_extract_none_row_when_no_tracks(self):
        import unittest.mock as mock
        with mock.patch("vitaldb_aki.data.tracks.first_available",
                        return_value=(None, [])):
            cfg = {"data": {"cache_dir": "/tmp"}}
            cases = {"1": {"caseid": "1", "anestart": 0.0, "opend": 600.0}}
            result = extract(cfg, cases, ["1"])
            self.assertIn("1", result)
            row = result["1"]
            self.assertEqual(row["mvcplx_available"], 0)
            for s in SPECS:
                if s.name != "mvcplx_available":
                    self.assertIsNone(row[s.name],
                                      f"{s.name} should be None when no tracks")

    def test_extract_none_row_when_no_opend(self):
        """No opend => no leakage cutoff => unavailable."""
        import unittest.mock as mock
        n = 200
        sig = [(i * 5.0, 80.0) for i in range(n)]
        with mock.patch("vitaldb_aki.data.tracks.first_available",
                        return_value=("Solar8000/ART_MBP", sig)):
            cfg = {"data": {"cache_dir": "/tmp"}}
            cases = {"1": {"caseid": "1"}}  # no opend
            result = extract(cfg, cases, ["1"])
            self.assertEqual(result["1"]["mvcplx_available"], 0)

    def test_extract_computes_when_three_core_tracks_present(self):
        """With MAP+HR+EtCO2 tracks and enough length, features are non-None."""
        import unittest.mock as mock

        n = 200
        dt = 5.0
        map_track = [(i * dt, 80.0 + 5.0 * math.sin(i * 0.12)) for i in range(n)]
        hr_track = [(i * dt, 70.0 + 4.0 * math.cos(i * 0.09)) for i in range(n)]
        etco2_track = [(i * dt, 35.0 + 2.0 * math.sin(i * 0.05)) for i in range(n)]

        def _first_available(cfg, cid, tnames, **kw):
            if any("MBP" in tn for tn in tnames):
                return ("Solar8000/ART_MBP", map_track)
            if any(tn.endswith("/HR") or "PLETH_HR" in tn for tn in tnames):
                return ("Solar8000/HR", hr_track)
            if any("ETCO2" in tn for tn in tnames):
                return ("Solar8000/ETCO2", etco2_track)
            return (None, [])

        with mock.patch("vitaldb_aki.data.tracks.first_available",
                        side_effect=_first_available):
            cfg = {"data": {"cache_dir": "/tmp"}}
            cases = {"42": {"caseid": "42", "anestart": 0.0, "opend": float(n * dt)}}
            result = extract(cfg, cases, ["42"])

        row = result["42"]
        self.assertEqual(row["mvcplx_available"], 1)
        self.assertEqual(row["mvcplx_n_signals"], 3)
        self.assertIsNotNone(row["mvcplx_joint_sampen"])
        self.assertIsNotNone(row["mvcplx_mean_pairwise_corr"])
        self.assertIsNotNone(row["mvcplx_corr_dispersion"])
        self.assertIsNotNone(row["mvcplx_max_pairwise_corr"])

    def test_extract_missing_case(self):
        """caseid not in cases_by_id => none row."""
        cfg = {"data": {"cache_dir": "/tmp"}}
        result = extract(cfg, {}, ["nope"])
        self.assertEqual(result["nope"]["mvcplx_available"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
