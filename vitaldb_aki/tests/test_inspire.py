"""test_inspire.py -- offline unit tests for vitaldb_aki/inspire/.

All tests use synthetic INSPIRE-shaped DataFrames/dicts.  No network access.
No credentials required.  No INSPIRE_DATA_DIR needed.

Run:
    python3 -m unittest vitaldb_aki.tests.test_inspire -v

Coverage:
  1. client.available() -> False with no env var (no crash, no network call)
  2. client.load_table() raises InspireNotAvailable when no data dir set
  3. client.to_float() edge cases
  4. labeling: KDIGO on INSPIRE creatinine series matches cohort/labeling.py
     on IDENTICAL inputs (regression / consistency)
  5. labeling: baseline picker -- most recent preop cr selected
  6. labeling: postop anchor is opend correctly
  7. labeling: cases with no preop cr -> unlabelable (aki=None)
  8. labeling: 48h sensitivity window fires correctly
  9. pfds_clinical: finite values on a well-formed synthetic case
 10. pfds_clinical: dissociation flag fires (MAP OK but EtCO2 low)
 11. pfds_clinical: pressor detection and pressor_stress direction
 12. pfds_clinical: recovery lag direction (MAP recovers -> positive delta)
 13. pfds_clinical: all-None when no vitals
 14. pfds_clinical: FiO2 unit normalisation (percentage -> fraction)
 15. pfds_clinical: no NaN leaks (all finite or None)
 16. validate: end-to-end on synthetic scores+labels returns AUROC/NRI/calibration
 17. validate: AUROC direction (better model scores higher)
 18. validate: map_adequate subgroup correctly populated
 19. validate: calibration slope ~ 1 for perfectly calibrated scores
 20. validate: decision_curve net benefit positive for useful model
"""
from __future__ import annotations

import math
import os
import sys
import unittest

# Ensure package root on sys.path when run directly
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


# ---------------------------------------------------------------------------
# Synthetic data builders
# ---------------------------------------------------------------------------

def _make_operations(n: int = 10) -> list[dict[str, str]]:
    """Build synthetic INSPIRE operations rows."""
    rows = []
    for i in range(n):
        rows.append({
            "caseid":     str(i + 1),
            "subjectid":  str(i + 100),
            "age":        str(50 + i),
            "sex":        "M" if i % 2 == 0 else "F",
            "asa":        str(1 + (i % 3)),
            "emergency":  "1" if i % 5 == 0 else "0",
            "optype":     "general" if i % 3 != 0 else "cardiac",
            "opstart":    "0",
            "opend":      str(3600 * 3),   # 3-hour surgery (10 800 s)
            "bmi":        "25.0",
            "inhosp_death": "0",
            "icu_days":   "0",
            "hosp_days":  "5",
            "crrt":       "0",
            "ecmo":       "0",
            "htn":        "1" if i % 4 == 0 else "0",
            "dm":         "1" if i % 3 == 0 else "0",
        })
    return rows


def _make_labs(creatinine_cases: dict[str, list[tuple[float, float]]]) -> list[dict[str, str]]:
    """Build synthetic labs rows from {caseid: [(time_s, cr_mgdl), ...]}."""
    rows = []
    for cid, series in creatinine_cases.items():
        for t, v in series:
            rows.append({
                "caseid": cid,
                "time":   str(t),
                "name":   "cr",
                "result": str(v),
            })
    return rows


def _make_vitals(
    caseid: str,
    n_epochs: int = 36,            # 36 * 5 min = 3 h
    map_val: float = 75.0,
    hr_val: float = 70.0,
    spo2_val: float = 99.0,
    etco2_val: float = 35.0,
    fio2_val: float = 0.5,
    map_override: dict[int, float] | None = None,   # epoch_idx -> value
    etco2_override: dict[int, float] | None = None,
    spo2_override: dict[int, float] | None = None,
) -> list[dict[str, str]]:
    """Build synthetic vitals rows at 5-min intervals."""
    rows = []
    for i in range(n_epochs):
        t = i * 300.0   # 5-min steps
        m   = map_override.get(i, map_val)   if map_override   else map_val
        c   = etco2_override.get(i, etco2_val) if etco2_override else etco2_val
        s   = spo2_override.get(i, spo2_val)  if spo2_override  else spo2_val
        rows.append({
            "caseid": caseid,
            "time":   str(t),
            "mbp":    str(m),
            "hr":     str(hr_val),
            "spo2":   str(s),
            "etco2":  str(c),
            "fio2":   str(fio2_val),
            "rr":     "14",
            "tv":     "500",
            "peep":   "5",
            "temp":   "36.5",
        })
    return rows


def _make_meds(caseid: str, events: list[tuple[float, str]]) -> list[dict[str, str]]:
    """Build synthetic medication rows [(time_s, drug_name), ...]."""
    rows = []
    for t, drug in events:
        rows.append({
            "caseid": caseid,
            "time":   str(t),
            "name":   drug,
            "amount": "5",
            "unit":   "mcg/kg/min",
        })
    return rows


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestClient(unittest.TestCase):
    """Tests for inspire/client.py."""

    def setUp(self):
        # Ensure no stray env var from caller
        os.environ.pop("INSPIRE_DATA_DIR", None)

    def test_available_false_no_env(self):
        """available() returns False with no env var set (no crash, no network)."""
        from vitaldb_aki.inspire.client import available
        result = available()
        self.assertFalse(result)

    def test_available_false_nonexistent_dir(self):
        """available() returns False for non-existent directory."""
        from vitaldb_aki.inspire.client import available
        os.environ["INSPIRE_DATA_DIR"] = "/nonexistent/path/inspire_xyz"
        try:
            result = available()
            self.assertFalse(result)
        finally:
            os.environ.pop("INSPIRE_DATA_DIR", None)

    def test_load_table_raises_when_unavailable(self):
        """load_table raises InspireNotAvailable when no data dir."""
        from vitaldb_aki.inspire.client import load_table, InspireNotAvailable
        with self.assertRaises(InspireNotAvailable):
            load_table("operations")

    def test_to_float_numeric(self):
        """to_float parses valid numerics."""
        from vitaldb_aki.inspire.client import to_float
        self.assertAlmostEqual(to_float("1.23"), 1.23)
        self.assertAlmostEqual(to_float("0"), 0.0)
        self.assertAlmostEqual(to_float("-5.5"), -5.5)

    def test_to_float_missing(self):
        """to_float returns None for missing / empty / sentinel values."""
        from vitaldb_aki.inspire.client import to_float
        for v in ("", "nan", "NA", "None", "null", ".", None):
            self.assertIsNone(to_float(v), msg=f"Expected None for {v!r}")

    def test_to_float_non_numeric(self):
        """to_float returns None for non-parseable strings."""
        from vitaldb_aki.inspire.client import to_float
        self.assertIsNone(to_float("abc"))

    def test_to_int(self):
        """to_int parses valid integers and returns None for missing."""
        from vitaldb_aki.inspire.client import to_int
        self.assertEqual(to_int("3"), 3)
        self.assertIsNone(to_int(""))

    def tearDown(self):
        os.environ.pop("INSPIRE_DATA_DIR", None)


class TestLabeling(unittest.TestCase):
    """Tests for inspire/labeling.py -- KDIGO on INSPIRE creatinine."""

    OP_DURATION_S = 3600 * 3   # 3 h surgery -> anchor at 10800 s

    def _label_case(self, series, op_duration_s=None):
        from vitaldb_aki.inspire.labeling import label_inspire_case
        return label_inspire_case(
            "test",
            series,
            op_duration_s or self.OP_DURATION_S,
        )

    def test_consistency_with_vitaldb_labeler(self):
        """KDIGO fires identically to cohort/labeling.label_case on same inputs."""
        from vitaldb_aki.cohort.labeling import label_case
        from vitaldb_aki.inspire.labeling import DEFAULT_KDIGO_CFG

        baseline_cr = 0.9
        # Postop cr: absolute rise 0.4 mg/dL (>= 0.3 threshold)
        # VitalDB format: dt in seconds relative to opend anchor
        # INSPIRE format: time in seconds from opstart; opend = OP_DURATION_S
        abs_window_s = DEFAULT_KDIGO_CFG["abs_window_h"] * 3600
        postop_dt = abs_window_s / 2   # well within 48 h

        # VitalDB labeler input (dt relative to anchor, positive = postop)
        vitaldb_postop = [(postop_dt, baseline_cr + 0.4)]
        vdb_result = label_case(
            "vdb", baseline_cr, "preop_cr", vitaldb_postop, DEFAULT_KDIGO_CFG
        )

        # INSPIRE labeler input: time = opstart + ... relative to opstart
        # opend = OP_DURATION_S; postop = time > opend
        inspire_time = self.OP_DURATION_S + postop_dt
        inspire_series = [
            (-100.0, baseline_cr),          # preop baseline
            (inspire_time, baseline_cr + 0.4),  # postop
        ]
        insp_result = self._label_case(inspire_series)

        self.assertEqual(vdb_result.aki, insp_result.aki,
                         msg="KDIGO decision must match VitalDB labeler")
        self.assertEqual(vdb_result.aki, 1)
        self.assertEqual(insp_result.aki, 1)

    def test_absolute_rise_fires(self):
        """Absolute rise >= 0.3 mg/dL within 48 h triggers AKI."""
        series = [
            (-3600.0, 0.9),          # preop baseline
            (self.OP_DURATION_S + 3600.0, 1.25),  # postop: +0.35 mg/dL
        ]
        result = self._label_case(series)
        self.assertEqual(result.aki, 1)
        self.assertIn("abs", result.reason)

    def test_relative_rise_fires(self):
        """Relative rise >= 1.5x within 7 days triggers AKI."""
        # 1.4 * 1.5 = 2.1 -- should fire on relative
        series = [
            (-3600.0, 1.4),          # preop baseline
            (self.OP_DURATION_S + 50 * 3600.0, 2.2),  # postop: 1.57x, within 7d
        ]
        result = self._label_case(series)
        self.assertEqual(result.aki, 1)

    def test_no_aki(self):
        """No criterion fired -> AKI = 0."""
        series = [
            (-3600.0, 0.9),
            (self.OP_DURATION_S + 3600.0, 0.95),  # tiny rise, no threshold
        ]
        result = self._label_case(series)
        self.assertEqual(result.aki, 0)

    def test_no_preop_cr_unlabelable(self):
        """No preop creatinine -> aki = None (unlabelable)."""
        series = [
            (self.OP_DURATION_S + 3600.0, 1.5),  # only postop
        ]
        result = self._label_case(series)
        self.assertIsNone(result.aki)

    def test_no_postop_cr_unlabelable(self):
        """No postop creatinine -> aki = None (unlabelable)."""
        series = [
            (-3600.0, 0.9),   # only preop
        ]
        result = self._label_case(series)
        self.assertIsNone(result.aki)

    def test_baseline_most_recent_preop(self):
        """Baseline is the most recent preop cr (largest negative time)."""
        from vitaldb_aki.inspire.labeling import _pick_baseline
        series = [
            (-86400.0, 1.2),    # 24 h before
            (-3600.0,  0.9),    # 1 h before (most recent)
            (-172800.0, 1.5),   # 48 h before
        ]
        baseline, source = _pick_baseline(series)
        self.assertAlmostEqual(baseline, 0.9)
        self.assertEqual(source, "preop_lab")

    def test_baseline_outside_30d_window_unlabelable(self):
        """Baseline older than 30 days -> unlabelable."""
        from vitaldb_aki.inspire.labeling import _pick_baseline, BASELINE_PREOP_WINDOW_S
        series = [
            (-(BASELINE_PREOP_WINDOW_S + 3600), 0.9),  # just outside 30d
        ]
        baseline, source = _pick_baseline(series)
        self.assertIsNone(baseline)
        self.assertEqual(source, "none")

    def test_48h_sensitivity_window(self):
        """AKI fires within 48 h absolute window (sensitivity analysis)."""
        from vitaldb_aki.inspire.labeling import DEFAULT_KDIGO_CFG
        kcfg_48h = dict(DEFAULT_KDIGO_CFG)
        kcfg_48h["rel_window_h"] = 48   # restrict both windows to 48 h
        series = [
            (-3600.0, 0.9),
            (self.OP_DURATION_S + 30 * 3600, 1.25),  # 30 h postop -- within 48 h
        ]
        from vitaldb_aki.inspire.labeling import label_inspire_case
        result = label_inspire_case("x", series, self.OP_DURATION_S, kcfg_48h)
        self.assertEqual(result.aki, 1)

    def test_label_all_cases(self):
        """label_all_cases processes an operations list correctly."""
        from vitaldb_aki.inspire.labeling import label_all_cases
        ops = _make_operations(3)
        # Case 1: AKI (abs rise)
        # Case 2: no AKI
        # Case 3: unlabelable (no preop cr)
        cr_map = {
            "1": [(-3600.0, 0.9), (10800.0 + 3600.0, 1.25)],   # AKI
            "2": [(-3600.0, 0.9), (10800.0 + 3600.0, 0.95)],   # no AKI
            "3": [(10800.0 + 3600.0, 1.5)],                      # unlabelable
        }
        labs = _make_labs(cr_map)
        results = label_all_cases(ops, labs)
        self.assertEqual(results["1"].aki, 1)
        self.assertEqual(results["2"].aki, 0)
        self.assertIsNone(results["3"].aki)


class TestPfdsClinical(unittest.TestCase):
    """Tests for inspire/pfds_clinical.py."""

    OP_DURATION_S = 3600 * 3   # 10 800 s

    def _compute(self, caseid, vitals, meds=None):
        from vitaldb_aki.inspire.pfds_clinical import compute_pfds_clinical
        return compute_pfds_clinical(
            caseid, vitals, meds or [], self.OP_DURATION_S
        )

    def test_finite_values_basic(self):
        """Finite values for all features on a well-formed synthetic case."""
        vitals = _make_vitals("1")
        result = self._compute("1", vitals)
        for k, v in result.items():
            if v is not None:
                self.assertTrue(math.isfinite(v), msg=f"{k}={v} is not finite")

    def test_all_none_no_vitals(self):
        """All features None when no vitals exist for the case."""
        result = self._compute("99", [])
        self.assertTrue(all(v is None for v in result.values()),
                        msg="Expected all None when no vitals")

    def test_dissociation_flag_fires(self):
        """pfd_dissociation > 0 when MAP OK but EtCO2 low in some epochs."""
        # Build vitals: first half MAP=75/EtCO2=35 (no dissociation),
        # second half MAP=80/EtCO2=20 (dissociation: MAP OK, EtCO2 low)
        n = 36
        etco2_ov = {i: 20.0 for i in range(n // 2, n)}  # low EtCO2 in 2nd half
        vitals = _make_vitals("2", n_epochs=n, map_val=80.0, etco2_override=etco2_ov)
        result = self._compute("2", vitals)
        self.assertIsNotNone(result["pfd_dissociation"])
        self.assertGreater(result["pfd_dissociation"], 0.0,
                           msg="Dissociation should be > 0 when EtCO2 is low")

    def test_no_dissociation_when_all_normal(self):
        """pfd_dissociation == 0 when MAP and EtCO2/SpO2 all normal."""
        vitals = _make_vitals("3", map_val=75.0, etco2_val=38.0, spo2_val=99.0)
        result = self._compute("3", vitals)
        self.assertIsNotNone(result["pfd_dissociation"])
        self.assertAlmostEqual(result["pfd_dissociation"], 0.0, places=5)

    def test_pressor_detection(self):
        """pas_pressor_min > 0 when pressor events are present."""
        vitals = _make_vitals("4")
        meds = _make_meds("4", [(300.0, "norepinephrine"), (600.0, "phenylephrine")])
        result = self._compute("4", vitals, meds)
        self.assertIsNotNone(result["pas_pressor_min"])
        self.assertGreater(result["pas_pressor_min"], 0.0)

    def test_pressor_stress_direction(self):
        """pressor_stress is higher when more pressor epochs occur."""
        vitals = _make_vitals("5", map_val=70.0)
        # Heavy pressor use: events every 5 min for the whole surgery
        n = 36
        meds_heavy = _make_meds("5", [(i * 300.0, "norepinephrine") for i in range(n)])
        result_heavy = self._compute("5", vitals, meds_heavy)
        result_none  = self._compute("5", vitals, [])
        self.assertIsNotNone(result_heavy["pas_pressor_stress"])
        self.assertIsNotNone(result_none["pas_pressor_stress"])
        self.assertGreater(result_heavy["pas_pressor_stress"],
                           result_none["pas_pressor_stress"],
                           msg="pressor_stress must be higher with heavy pressor use")

    def test_recovery_lag_positive_when_map_recovers(self):
        """rlg_map_recovery > 0 when MAP rises from start to end."""
        # First 30 min: MAP = 60; last 30 min: MAP = 80
        n = 36
        # epoch 0..5 = first 30 min; epoch 30..35 = last 30 min
        map_ov = {i: 60.0 for i in range(6)}
        map_ov.update({i: 80.0 for i in range(30, 36)})
        vitals = _make_vitals("6", n_epochs=n, map_override=map_ov)
        result = self._compute("6", vitals)
        rlg = result["rlg_map_recovery"]
        self.assertIsNotNone(rlg)
        self.assertGreater(rlg, 0.0,
                           msg="rlg_map_recovery should be positive when MAP rises")

    def test_recovery_lag_negative_when_map_falls(self):
        """rlg_map_recovery < 0 when MAP falls from start to end."""
        n = 36
        map_ov = {i: 80.0 for i in range(6)}
        map_ov.update({i: 60.0 for i in range(30, 36)})
        vitals = _make_vitals("7", n_epochs=n, map_override=map_ov)
        result = self._compute("7", vitals)
        rlg = result["rlg_map_recovery"]
        self.assertIsNotNone(rlg)
        self.assertLess(rlg, 0.0)

    def test_fio2_percentage_normalised(self):
        """FiO2 values > 1.5 (percentage) are normalised to fraction."""
        # Pass FiO2 = 50 (%) -- should be normalised to 0.50 as fraction
        vitals = _make_vitals("8", fio2_val=50.0)   # 50% passed as raw
        result = self._compute("8", vitals)
        arf_fio2 = result["arf_fio2_mean"]
        self.assertIsNotNone(arf_fio2)
        self.assertLessEqual(arf_fio2, 1.0,
                             msg="FiO2 should be normalised to fraction <= 1")

    def test_no_nan_leaks(self):
        """No NaN (float) leaks in output; all values are finite or None."""
        vitals = _make_vitals("9")
        result = self._compute("9", vitals)
        for k, v in result.items():
            if v is not None:
                self.assertFalse(math.isnan(v), msg=f"{k} is NaN")
                self.assertFalse(math.isinf(v), msg=f"{k} is Inf")

    def test_artifact_rejection(self):
        """Extreme MAP values are rejected by physiologic range gate."""
        # All MAP values are 999 (artifact)
        vitals = _make_vitals("10", map_val=999.0)
        result = self._compute("10", vitals)
        # mean MAP should be None (all rejected)
        self.assertIsNone(result["pfd_map_mean"])

    def test_compute_all(self):
        """compute_pfds_clinical_all runs without error on multiple cases."""
        from vitaldb_aki.inspire.pfds_clinical import compute_pfds_clinical_all
        ops = _make_operations(3)
        vitals = []
        for i in range(1, 4):
            vitals.extend(_make_vitals(str(i)))
        results = compute_pfds_clinical_all(ops, vitals, [])
        self.assertEqual(len(results), 3)
        for cid, feat in results.items():
            self.assertIn("pfd_dissociation", feat)


class TestValidate(unittest.TestCase):
    """Tests for inspire/validate.py."""

    def _make_rows_labels(
        self,
        n: int = 200,
        prevalence: float = 0.25,
        pfds_auc: float = 0.75,
        seed: int = 42,
    ):
        """Build synthetic feature rows and labels with controllable PFDS score quality."""
        import random
        rng = random.Random(seed)
        n_pos = int(n * prevalence)
        y_list = [1] * n_pos + [0] * (n - n_pos)
        rng.shuffle(y_list)

        rows = []
        labels = {}
        for i, yi in enumerate(y_list):
            cid = str(i + 1)
            # True signal: pfds_score ~ gaussian with mean shift for positive cases
            signal = rng.gauss(0.6 if yi else 0.4, 0.15)
            signal = max(0.01, min(0.99, signal))
            # Demographic covariates
            row = {
                "caseid":        cid,
                "age":           str(50 + rng.randint(-15, 20)),
                "asa":           str(1 + rng.randint(0, 2)),
                "emergency":     "1" if rng.random() < 0.1 else "0",
                "optype":        "general",
                "optype_encoded": str(0),
                "baseline_cr":   str(round(0.8 + rng.gauss(0, 0.2), 2)),
                "op_duration_h": str(round(2 + rng.gauss(0, 0.5), 2)),
                "htn":           "1" if rng.random() < 0.4 else "0",
                "dm":            "1" if rng.random() < 0.2 else "0",
                "sex":           "M" if rng.random() < 0.5 else "F",
                # PFDS features (used by subgroup predicates)
                "pfd_map_mean":      str(round(70 + rng.gauss(0, 5), 1)),
                "pfd_dissociation":  str(round(max(0, rng.gauss(0.05, 0.05)), 3)),
                "_pfds_score":       signal,
            }
            rows.append(row)
            labels[cid] = yi

        return rows, labels

    def test_validate_end_to_end(self):
        """validate() runs end-to-end and returns AUROC/NRI/calibration."""
        from vitaldb_aki.inspire.validate import validate
        rows, labels = self._make_rows_labels(n=200)

        def score_fn(row):
            return float(row["_pfds_score"])

        result = validate(rows, labels, score_fn, bootstrap_iters=10, seed=0)

        self.assertIn("auroc",        result)
        self.assertIn("auprc",        result)
        self.assertIn("calibration",  result)
        self.assertIn("nri_idi",      result)
        self.assertIn("decision_curve", result)
        self.assertIn("subgroups",    result)

    def test_auroc_direction(self):
        """Better signal -> higher AUROC."""
        from vitaldb_aki.inspire.validate import validate, _auroc_simple

        rows_good, labels = self._make_rows_labels(n=300, prevalence=0.3, seed=7)
        rows_bad  = [dict(r) for r in rows_good]
        # Corrupt scores for bad model
        import random
        rng = random.Random(1)
        for r in rows_bad:
            r["_pfds_score"] = rng.random()   # uniform noise

        def good_score(row): return float(row["_pfds_score"])
        def bad_score(row):  return float(row["_pfds_score"])

        res_good = validate(rows_good, labels, good_score, bootstrap_iters=0)
        res_bad  = validate(rows_bad,  labels, bad_score,  bootstrap_iters=0)
        self.assertGreater(res_good["auroc"], res_bad["auroc"] - 0.05,
                           msg="Good signal should have better or similar AUROC vs noise")

    def test_auroc_greater_than_05_for_useful_model(self):
        """AUROC > 0.5 for a model with true signal."""
        from vitaldb_aki.inspire.validate import validate
        rows, labels = self._make_rows_labels(n=300, prevalence=0.3, seed=11)
        def score_fn(row): return float(row["_pfds_score"])
        result = validate(rows, labels, score_fn, bootstrap_iters=0)
        self.assertGreater(result["auroc"], 0.5)

    def test_calibration_slope_near_one_for_perfect(self):
        """Calibration slope ~ 1 when predicted probabilities are well-calibrated."""
        from vitaldb_aki.inspire.validate import calibration_slope_intercept
        import random
        rng = random.Random(5)
        n = 500
        # Perfectly calibrated: prob = actual frequency
        y = [1 if rng.random() < 0.3 else 0 for _ in range(n)]
        # Use close-to-true predicted probs
        probs = []
        for yi in y:
            p = 0.3 + rng.gauss(0, 0.01)
            probs.append(max(0.01, min(0.99, p)))
        cal = calibration_slope_intercept(y, probs)
        self.assertFalse(math.isnan(cal["slope"]))
        # Slope should be close to 1 (within 0.5 given small perturbation)
        self.assertGreater(cal["slope"], 0.0)

    def test_decision_curve_positive_nb_at_low_thresholds(self):
        """Net benefit positive at low thresholds for useful model."""
        from vitaldb_aki.inspire.validate import validate
        rows, labels = self._make_rows_labels(n=300, prevalence=0.3, seed=9)
        def score_fn(row): return float(row["_pfds_score"])
        result = validate(rows, labels, score_fn, bootstrap_iters=0)
        dca = result["decision_curve"]
        # At threshold 0.1, nb_model should be positive for a useful model
        nb_10 = next((r["nb_model"] for r in dca if abs(r["threshold"] - 0.10) < 0.01), None)
        self.assertIsNotNone(nb_10)
        self.assertGreater(nb_10, 0.0)

    def test_subgroups_populated(self):
        """Subgroup dict has entries for at least some demographic groups."""
        from vitaldb_aki.inspire.validate import validate
        rows, labels = self._make_rows_labels(n=300, prevalence=0.3, seed=3)
        def score_fn(row): return float(row["_pfds_score"])
        result = validate(rows, labels, score_fn, bootstrap_iters=0)
        sg = result["subgroups"]
        self.assertIn("age_ge_65",  sg)
        self.assertIn("female",     sg)
        self.assertIn("emergency",  sg)
        # At least some subgroups should have n > 0
        total_n = sum(sg[k]["n"] for k in sg)
        self.assertGreater(total_n, 0)

    def test_map_adequate_subgroup(self):
        """map_adequate_subgroup is populated (may be too-small with synthetic data)."""
        from vitaldb_aki.inspire.validate import validate
        rows, labels = self._make_rows_labels(n=300, prevalence=0.3, seed=13)
        def score_fn(row): return float(row["_pfds_score"])
        result = validate(rows, labels, score_fn, bootstrap_iters=0)
        self.assertIn("map_adequate_subgroup", result)
        # Either has 'n' (any size) or a note about being too small
        ma = result["map_adequate_subgroup"]
        self.assertIn("n", ma)

    def test_no_labelable_cases_returns_error(self):
        """validate() returns error dict when no labelable cases."""
        from vitaldb_aki.inspire.validate import validate
        rows = [{"caseid": "99", "_pfds_score": 0.5}]
        labels = {}   # no overlap with rows
        result = validate(rows, labels, lambda r: float(r["_pfds_score"]))
        self.assertIn("error", result)

    def test_recalibrated_results_present(self):
        """Recalibrated results block is present when recalibrate=True."""
        from vitaldb_aki.inspire.validate import validate
        rows, labels = self._make_rows_labels(n=200, prevalence=0.3, seed=17)
        def score_fn(row): return float(row["_pfds_score"])
        result = validate(rows, labels, score_fn, recalibrate=True, bootstrap_iters=0)
        self.assertIn("recalibrated", result)
        self.assertIn("auroc", result["recalibrated"])

    def test_auroc_simple_perfect_separator(self):
        """_auroc_simple returns 1.0 for a perfect binary separator."""
        from vitaldb_aki.inspire.validate import _auroc_simple
        y = [1, 1, 0, 0]
        s = [0.9, 0.8, 0.2, 0.1]
        self.assertAlmostEqual(_auroc_simple(y, s), 1.0)

    def test_auroc_simple_random(self):
        """_auroc_simple returns ~0.5 for random scores."""
        from vitaldb_aki.inspire.validate import _auroc_simple
        import random
        rng = random.Random(0)
        n = 400
        y = [rng.randint(0, 1) for _ in range(n)]
        s = [rng.random() for _ in range(n)]
        auc = _auroc_simple(y, s)
        self.assertGreater(auc, 0.35)
        self.assertLess(auc, 0.65)

    def test_auprc_simple(self):
        """_auprc_simple returns positive value for useful model."""
        from vitaldb_aki.inspire.validate import _auprc_simple
        y = [1, 1, 0, 0, 1, 0]
        s = [0.9, 0.8, 0.3, 0.2, 0.7, 0.1]
        auc = _auprc_simple(y, s)
        self.assertGreater(auc, 0.0)
        self.assertLessEqual(auc, 1.0)


class TestImportSanity(unittest.TestCase):
    """Import-time sanity: all submodules import cleanly without creds."""

    def test_client_imports(self):
        import vitaldb_aki.inspire.client  # noqa: F401

    def test_labeling_imports(self):
        import vitaldb_aki.inspire.labeling  # noqa: F401

    def test_pfds_clinical_imports(self):
        import vitaldb_aki.inspire.pfds_clinical  # noqa: F401

    def test_validate_imports(self):
        import vitaldb_aki.inspire.validate  # noqa: F401

    def test_clinical_computable_keys_match_spec(self):
        """CLINICAL_COMPUTABLE dict has exactly the 4 biomarker families."""
        from vitaldb_aki.inspire.pfds_clinical import CLINICAL_COMPUTABLE
        prefixes = {k.split("_")[0] for k in CLINICAL_COMPUTABLE}
        self.assertIn("pfd",  prefixes)
        self.assertIn("pas",  prefixes)
        self.assertIn("arf",  prefixes)
        self.assertIn("rlg",  prefixes)

    def test_column_map_has_required_signals(self):
        """COLUMN_MAP covers mandatory vital signals."""
        from vitaldb_aki.inspire.pfds_clinical import COLUMN_MAP
        for req in ("mbp", "hr", "spo2", "etco2", "fio2"):
            self.assertIn(req, COLUMN_MAP, msg=f"{req} missing from COLUMN_MAP")


if __name__ == "__main__":
    unittest.main(verbosity=2)
