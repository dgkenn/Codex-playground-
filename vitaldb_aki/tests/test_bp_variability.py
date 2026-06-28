"""test_bp_variability.py -- Offline unit tests for the BP-variability family (§7C).

All tests are pure-math / in-memory; no network access, no VitalDB downloads.
Each pure helper is tested against hand-built synthetic series with a KNOWN
expected direction (low-variability vs high-variability; regular vs irregular).

Run with:
    python3 -m unittest vitaldb_aki.tests.test_bp_variability -v
"""
from __future__ import annotations

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from vitaldb_aki.features.bp_variability import (
    # Module-level constants
    SPECS, MIN_SAMPLES, SAMPEN_M, SAMPEN_R_FRAC, MAX_SAMPEN_LEN,
    MAP_MIN, MAP_MAX, HR_MIN, HR_MAX,
    # Pure helpers
    _mean,
    _sd,
    _cv,
    _arv,
    _rmssd,
    _uniform_cap,
    _sample_entropy,
    _ordered_values,
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

    def test_no_duplicate_names(self):
        names = [s.name for s in SPECS]
        self.assertEqual(len(names), len(set(names)),
                         "Duplicate feature names in BP-variability SPECS")

    def test_first_spec_is_available(self):
        self.assertEqual(SPECS[0].name, "bpv_available",
                         "First spec MUST be bpv_available")

    def test_all_comprehensive_tier(self):
        for s in SPECS:
            self.assertEqual(s.fset, "comprehensive",
                             msg=f"{s.name} fset={s.fset!r}; expected comprehensive")

    def test_required_features_present(self):
        names = {s.name for s in SPECS}
        required = {
            "bpv_available",
            "bpv_map_sd", "bpv_map_cv", "bpv_map_arv", "bpv_map_succ_var",
            "bpv_map_sampen",
            "bpv_hr_sd", "bpv_hr_arv", "bpv_hr_sampen",
        }
        missing = required - names
        self.assertFalse(missing, f"Missing BP-variability specs: {missing}")

    def test_spec_count(self):
        self.assertEqual(len(SPECS), 9, "Expected exactly 9 BP-variability specs")


# ===========================================================================
# 2. _mean / _sd / _cv on low- vs high-variability series
# ===========================================================================

class TestDispersion(unittest.TestCase):
    def test_mean_basic(self):
        self.assertAlmostEqual(_mean([10.0, 20.0, 30.0]), 20.0, places=9)

    def test_mean_empty_none(self):
        self.assertIsNone(_mean([]))

    def test_sd_constant_is_zero(self):
        self.assertAlmostEqual(_sd([80.0] * 10), 0.0, places=9)

    def test_sd_none_when_too_few(self):
        self.assertIsNone(_sd([80.0]))
        self.assertIsNone(_sd([]))

    def test_sd_low_vs_high_variability(self):
        """A tight series has lower SD than a noisy series at the same mean."""
        low = [80.0, 81.0, 79.0, 80.0, 81.0, 79.0]      # tight band
        high = [60.0, 100.0, 55.0, 105.0, 58.0, 102.0]  # wide swings
        sd_low = _sd(low)
        sd_high = _sd(high)
        self.assertIsNotNone(sd_low)
        self.assertIsNotNone(sd_high)
        self.assertLess(sd_low, sd_high,
                        "Low-variability series must have smaller SD")

    def test_sd_known_value(self):
        # population SD of [2,4,4,4,5,5,7,9] is 2.0 (classic example)
        self.assertAlmostEqual(_sd([2, 4, 4, 4, 5, 5, 7, 9]), 2.0, places=9)

    def test_cv_removes_level(self):
        """Same relative spread but doubled level => same CV."""
        a = [40.0, 60.0, 50.0]
        b = [80.0, 120.0, 100.0]  # exactly 2x
        cv_a = _cv(a)
        cv_b = _cv(b)
        self.assertIsNotNone(cv_a)
        self.assertIsNotNone(cv_b)
        self.assertAlmostEqual(cv_a, cv_b, places=9,
                               msg="CV must be invariant to overall level scaling")

    def test_cv_none_when_mean_zero(self):
        self.assertIsNone(_cv([-5.0, 5.0]))  # mean ~ 0

    def test_cv_none_when_too_few(self):
        self.assertIsNone(_cv([80.0]))


# ===========================================================================
# 3. _arv (Average Real Variability) -- explicit
# ===========================================================================

class TestARV(unittest.TestCase):
    def test_arv_known_value(self):
        """ARV of [80, 82, 79, 85] = mean(|2|,|−3|,|6|) = (2+3+6)/3 = 11/3."""
        series = [80.0, 82.0, 79.0, 85.0]
        self.assertAlmostEqual(_arv(series), (2 + 3 + 6) / 3.0, places=9)

    def test_arv_constant_is_zero(self):
        self.assertAlmostEqual(_arv([70.0] * 12), 0.0, places=9)

    def test_arv_none_when_too_few(self):
        self.assertIsNone(_arv([80.0]))
        self.assertIsNone(_arv([]))

    def test_arv_low_vs_high(self):
        """Regular series has lower ARV than an alternating/noisy series."""
        regular = [80.0, 80.5, 81.0, 80.5, 80.0, 80.5]
        noisy = [60.0, 100.0, 60.0, 100.0, 60.0, 100.0]  # 40-unit jumps
        arv_reg = _arv(regular)
        arv_noisy = _arv(noisy)
        self.assertIsNotNone(arv_reg)
        self.assertIsNotNone(arv_noisy)
        self.assertLess(arv_reg, arv_noisy,
                        "Regular series must have lower ARV than noisy series")

    def test_arv_is_order_sensitive(self):
        """ARV depends on time ordering; a sorted version differs from shuffled."""
        ordered = [10.0, 11.0, 12.0, 13.0]          # ARV = 1.0
        jagged = [10.0, 13.0, 11.0, 12.0]           # ARV = (3+2+1)/3 = 2.0
        self.assertAlmostEqual(_arv(ordered), 1.0, places=9)
        self.assertAlmostEqual(_arv(jagged), 2.0, places=9)
        self.assertNotAlmostEqual(_arv(ordered), _arv(jagged), places=6)

    def test_arv_robust_vs_sd_to_single_outlier(self):
        """A single spike inflates SD's successive structure less than RMSSD;
        here we just confirm ARV stays finite and ordered as expected."""
        with_spike = [80.0, 80.0, 80.0, 200.0 - 120.0, 80.0]  # one 80->80 etc
        self.assertIsNotNone(_arv(with_spike))


# ===========================================================================
# 4. _rmssd
# ===========================================================================

class TestRMSSD(unittest.TestCase):
    def test_rmssd_known_value(self):
        """RMSSD of [80, 82, 79] = sqrt(mean(2^2, 3^2)) = sqrt((4+9)/2)."""
        series = [80.0, 82.0, 79.0]
        self.assertAlmostEqual(_rmssd(series), math.sqrt((4 + 9) / 2.0), places=9)

    def test_rmssd_constant_is_zero(self):
        self.assertAlmostEqual(_rmssd([70.0] * 8), 0.0, places=9)

    def test_rmssd_none_when_too_few(self):
        self.assertIsNone(_rmssd([80.0]))

    def test_rmssd_low_vs_high(self):
        regular = [80.0, 80.5, 81.0, 80.5, 80.0]
        noisy = [60.0, 100.0, 60.0, 100.0, 60.0]
        self.assertLess(_rmssd(regular), _rmssd(noisy))

    def test_rmssd_ge_arv(self):
        """By Jensen/QM-AM, RMSSD >= ARV for any series."""
        series = [70.0, 75.0, 60.0, 90.0, 65.0, 80.0]
        self.assertGreaterEqual(_rmssd(series) + 1e-9, _arv(series))


# ===========================================================================
# 5. _uniform_cap
# ===========================================================================

class TestUniformCap(unittest.TestCase):
    def test_no_cap_when_short(self):
        s = [float(i) for i in range(10)]
        self.assertEqual(_uniform_cap(s, maxlen=100), s)

    def test_cap_reduces_length(self):
        s = [float(i) for i in range(10000)]
        capped = _uniform_cap(s, maxlen=3000)
        self.assertLessEqual(len(capped), 3000)
        self.assertGreater(len(capped), 0)

    def test_cap_is_deterministic(self):
        s = [float(i) for i in range(5000)]
        self.assertEqual(_uniform_cap(s, 1000), _uniform_cap(s, 1000))

    def test_cap_uses_stride_from_start(self):
        s = [float(i) for i in range(10)]
        # maxlen=5 -> stride=ceil(10/5)=2 -> [0,2,4,6,8]
        self.assertEqual(_uniform_cap(s, maxlen=5), [0.0, 2.0, 4.0, 6.0, 8.0])

    def test_cap_at_default_maxlen(self):
        # Lowered 3000 -> 2000 alongside the numpy vectorization: the match
        # matrix is O(n^2) in memory, so the cap bounds peak memory too.
        self.assertEqual(MAX_SAMPEN_LEN, 2000)


# ===========================================================================
# 6. _sample_entropy -- explicit (regular vs irregular; constant; empty)
# ===========================================================================

class TestSampleEntropy(unittest.TestCase):
    def test_constant_series_is_zero(self):
        """A perfectly constant series is maximally regular => SampEn == 0."""
        result = _sample_entropy([50.0] * 200, m=2, r=None)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 0.0, places=9,
                               msg="Constant series must give SampEn = 0 (max regular)")

    def test_near_constant_low_sampen(self):
        """A near-constant (tiny noise) series has very low SampEn."""
        # Slowly drifting, highly predictable series.
        series = [50.0 + 0.01 * math.sin(i / 5.0) for i in range(300)]
        result = _sample_entropy(series, m=2, r=None)
        self.assertIsNotNone(result)
        self.assertLess(result, 0.5,
                        "A near-constant smooth series should have low SampEn")

    def test_regular_lower_than_noisy(self):
        """A clean periodic series is MORE regular (lower SampEn) than noise."""
        # Regular: a smooth sine wave.
        regular = [50.0 + 10.0 * math.sin(i / 8.0) for i in range(400)]
        # Irregular: a deterministic pseudo-random walk (no numpy).
        noisy: list[float] = []
        x = 12345
        val = 50.0
        for _ in range(400):
            x = (1103515245 * x + 12345) % (2 ** 31)
            step = ((x / (2 ** 31)) - 0.5) * 40.0  # +-20 swings
            val = 50.0 + step
            noisy.append(val)
        sampen_reg = _sample_entropy(regular, m=2, r=None)
        sampen_noisy = _sample_entropy(noisy, m=2, r=None)
        self.assertIsNotNone(sampen_reg)
        self.assertIsNotNone(sampen_noisy)
        self.assertLess(sampen_reg, sampen_noisy,
                        "Regular sine must have lower SampEn than noisy series")

    def test_alternating_series_low_sampen(self):
        """A strict 2-cycle alternation is perfectly predictable => low SampEn."""
        series = [60.0, 100.0] * 150
        result = _sample_entropy(series, m=2, r=None)
        # Alternating is highly regular (each template predicts the next).
        self.assertIsNotNone(result)
        self.assertLess(result, 0.5,
                        "Strictly alternating series should be very regular")

    def test_empty_series_none(self):
        self.assertIsNone(_sample_entropy([], m=2, r=None))

    def test_too_short_none(self):
        # n < m + 2 => None
        self.assertIsNone(_sample_entropy([1.0, 2.0, 3.0], m=2, r=None))

    def test_long_series_capped_and_finite(self):
        """A long series is capped before the O(n^2) match and returns finite."""
        series = [50.0 + 5.0 * math.sin(i / 30.0) for i in range(20000)]
        result = _sample_entropy(series, m=2, r=None)
        self.assertIsNotNone(result)
        self.assertGreaterEqual(result, 0.0)

    def test_explicit_r_tolerance_respected(self):
        """A huge r makes every template match => A/B -> 1 => SampEn -> 0."""
        series = [50.0 + 10.0 * math.sin(i / 7.0) for i in range(200)]
        result = _sample_entropy(series, m=2, r=1e9)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 0.0, places=6,
                               msg="With enormous r every template matches => SampEn ~ 0")

    def test_vectorized_matches_pure_python(self):
        """The numpy-vectorized SampEn is bit-equivalent to a reference pure-Python
        Richman-Moorman counter on a non-trivial series (exact, no cap)."""
        series = [50.0 + 8.0 * math.sin(i / 9.0) + ((i * 1103515245 + 12345)
                  % 1000) / 250.0 for i in range(500)]

        def _ref(s, m=2):
            n = len(s)
            mu = sum(s) / n
            r = 0.2 * math.sqrt(sum((v - mu) ** 2 for v in s) / n)

            def mf(mm):
                last = n - mm + 1
                cnt = 0
                for i in range(last):
                    ti = s[i:i + mm]
                    for j in range(i + 1, last):
                        if all(abs(ti[k] - s[j + k]) <= r for k in range(mm)):
                            cnt += 1
                return cnt, last * (last - 1) // 2

            bc, bt = mf(m)
            ac, at = mf(m + 1)
            return -math.log((ac / at) / (bc / bt))

        ref = _ref(series)
        got = _sample_entropy(series, m=2, r=None)
        self.assertIsNotNone(got)
        self.assertAlmostEqual(got, ref, places=12,
                               msg="Vectorized SampEn must equal pure-Python reference")


# ===========================================================================
# 6b. POISON-PILL regression: a degenerate / flat series must return fast with a
#     sensible value (0.0 or None) and never hang. (Reproduces the case ~#962
#     where _sample_entropy on a flat MAP/HR series never returned.)
# ===========================================================================

class TestSampleEntropyDegenerateGuards(unittest.TestCase):
    def test_constant_series_returns_zero_fast(self):
        """A perfectly constant (SD==0) series short-circuits to 0.0 WITHOUT the
        O(n^2) match -- the poison-pill fix."""
        import time
        series = [70.0] * 3000  # the pathological flat MAP/HR record
        t0 = time.perf_counter()
        result = _sample_entropy(series, m=2, r=None)
        dt = time.perf_counter() - t0
        self.assertEqual(result, 0.0, "Constant series must give SampEn 0.0")
        self.assertLess(dt, 0.1, "Constant-series guard must be near-instant (no hang)")

    def test_all_identical_values_returns_zero(self):
        series = [42.0] * 2500
        self.assertEqual(_sample_entropy(series, m=2, r=None), 0.0)

    def test_all_match_within_r_returns_zero_fast(self):
        """When every length-m pair matches (tolerance r dwarfs the spread), the
        all-match short-circuit returns 0.0 without computing the second (m+1)
        match matrix. (A non-constant series only hits this with an externally
        large r; with auto r=0.2*SD only an exactly-constant series all-matches.)"""
        import time
        series = [75.0 + 2.0 * math.sin(i / 11.0) for i in range(2000)]
        t0 = time.perf_counter()
        result = _sample_entropy(series, m=2, r=1e6)  # r >> spread => all match
        dt = time.perf_counter() - t0
        self.assertEqual(result, 0.0,
                         "All-match series (huge r) must give SampEn 0.0")
        self.assertLess(dt, 0.3, "All-match short-circuit must be fast")

    def test_non_finite_values_dropped(self):
        """NaN / inf samples are dropped before the match; a constant remainder
        still yields a sensible value (0.0), not a crash or hang."""
        series = [70.0] * 100 + [float("nan"), float("inf")] + [70.0] * 100
        result = _sample_entropy(series, m=2, r=None)
        self.assertEqual(result, 0.0)

    def test_too_short_after_finite_filter_none(self):
        series = [float("nan"), 1.0, float("inf")]
        self.assertIsNone(_sample_entropy(series, m=2, r=None))

    def test_cap_lowered_to_2000(self):
        """A very long series is decimated to <= MAX_SAMPEN_LEN (=2000) points."""
        self.assertEqual(MAX_SAMPEN_LEN, 2000)
        capped = _uniform_cap([float(i) for i in range(50000)], MAX_SAMPEN_LEN)
        self.assertLessEqual(len(capped), 2000)


# ===========================================================================
# 7. _ordered_values
# ===========================================================================

class TestOrderedValues(unittest.TestCase):
    def test_sorts_by_time(self):
        samples = [(30.0, 2.0), (0.0, 1.0), (60.0, 3.0)]
        self.assertEqual(_ordered_values(samples), [1.0, 2.0, 3.0])

    def test_empty(self):
        self.assertEqual(_ordered_values([]), [])

    def test_arv_on_ordered_values_matches(self):
        """End-to-end: out-of-order samples sorted then ARV computed correctly."""
        samples = [(60.0, 85.0), (0.0, 80.0), (30.0, 82.0)]
        vals = _ordered_values(samples)  # [80, 82, 85]
        self.assertAlmostEqual(_arv(vals), (2 + 3) / 2.0, places=9)


# ===========================================================================
# 8. Constants sanity
# ===========================================================================

class TestConstants(unittest.TestCase):
    def test_physiologic_gates(self):
        self.assertEqual((MAP_MIN, MAP_MAX), (20.0, 200.0))
        self.assertEqual((HR_MIN, HR_MAX), (20.0, 220.0))

    def test_min_samples(self):
        self.assertEqual(MIN_SAMPLES, 30)

    def test_sampen_params(self):
        self.assertEqual(SAMPEN_M, 2)
        self.assertAlmostEqual(SAMPEN_R_FRAC, 0.2, places=9)


if __name__ == "__main__":
    unittest.main(verbosity=2)
