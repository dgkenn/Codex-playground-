"""test_build_matrix.py -- offline tests for inspire/build_matrix.py.

Two layers (mirrors test_inspire.py / test_external_validation.py):
  * STDLIB-light pure helpers: gz_ok, _ckd_epi_2021, _pick_baseline_cr, _f.
  * SCIENCE-STACK end-to-end: build a TINY synthetic raw INSPIRE directory
    (operations/labs gz, no vitals) and assert build_inspire_matrix produces a
    matrix with the expected columns, the PENDING-vitals path (empty MAP cols),
    and correct KDIGO renal labels with the MINUTES time unit.

No network, no credentials, no real INSPIRE data.  Never touches cache/inspire_raw.
"""
from __future__ import annotations

import gzip
import os
import sys
import tempfile
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from vitaldb_aki.inspire import build_matrix as bm

try:
    import numpy  # noqa: F401
    import pandas  # noqa: F401
    _HAVE_SCI = True
except Exception:
    _HAVE_SCI = False


class TestPureHelpers(unittest.TestCase):
    def test_gz_ok_detects_bad_and_good(self):
        with tempfile.TemporaryDirectory() as d:
            good = os.path.join(d, "good.csv.gz")
            with gzip.open(good, "wt") as fh:
                fh.write("a,b\n1,2\n")
            self.assertTrue(bm.gz_ok(good))

            bad = os.path.join(d, "bad.csv.gz")
            with open(bad, "wb") as fh:
                fh.write(b"\x1f\x8b\x08not-a-real-gzip-stream")
            self.assertFalse(bm.gz_ok(bad))

            self.assertFalse(bm.gz_ok(os.path.join(d, "absent.csv.gz")))

    def test_ckd_epi_monotone_and_ckd_flag(self):
        # higher creatinine -> lower eGFR
        hi = bm._ckd_epi_2021(0.8, 50, female=False)
        lo = bm._ckd_epi_2021(2.5, 50, female=False)
        self.assertIsNotNone(hi)
        self.assertIsNotNone(lo)
        self.assertGreater(hi, lo)
        # a clearly impaired case is < 60 (CKD)
        self.assertLess(bm._ckd_epi_2021(3.0, 70, female=False), 60.0)
        # missing inputs -> None
        self.assertIsNone(bm._ckd_epi_2021(None, 50, False))

    def test_pick_baseline_most_recent_preop_minutes(self):
        # times in MINUTES; anchor at 1000
        series = [(100, 0.8), (900, 1.0), (1100, 2.0)]  # 1100 is postop -> ignored
        self.assertEqual(bm._pick_baseline_cr(series, 1000), 1.0)
        # nothing before anchor -> None
        self.assertIsNone(bm._pick_baseline_cr([(1100, 1.0)], 1000))
        # outside the 365d preop window -> None
        far = -(bm.BASELINE_PREOP_WINDOW_MIN + 10)
        self.assertIsNone(bm._pick_baseline_cr([(far, 1.0)], 0))

    def test_f_parsing(self):
        self.assertEqual(bm._f("1.5"), 1.5)
        self.assertIsNone(bm._f(""))
        self.assertIsNone(bm._f("nan"))
        self.assertIsNone(bm._f(None))


def _write_gz_csv(path, header, rows):
    with gzip.open(path, "wt", newline="") as fh:
        fh.write(",".join(header) + "\n")
        for r in rows:
            fh.write(",".join(str(x) for x in r) + "\n")


@unittest.skipUnless(_HAVE_SCI, "needs pandas/numpy")
class TestEndToEndNoVitals(unittest.TestCase):
    """Build a tiny raw dir WITHOUT vitals -> PENDING-vitals path."""

    def _build_raw(self, d):
        # operations: 2 ops (minutes time unit). op A: AKI subject; op B: clean.
        ops_header = ["op_id", "subject_id", "hadm_id", "case_id", "opdate", "age",
                      "sex", "weight", "height", "race", "asa", "emop", "department",
                      "antype", "icd10_pcs", "orin_time", "orout_time", "opstart_time",
                      "opend_time", "admission_time", "discharge_time", "anstart_time",
                      "anend_time", "cpbon_time", "cpboff_time", "icuin_time",
                      "icuout_time", "inhosp_death_time", "allcause_death_time"]
        ops_rows = [
            # op A subject 100: opstart 1140, opend 1230, anstart 1120, anend 1235
            [400001, 100, 200, "", 0, 65, "M", 70, 170, "Asian", 3, 0, "GS",
             "General", "0X", 1110, 1245, 1140, 1230, 0, 5000, 1120, 1235,
             "", "", "", "", "", ""],
            # op B subject 101: clean
            [400002, 101, 201, "", 0, 50, "F", 60, 160, "Asian", 2, 0, "OS",
             "General", "0Y", 1110, 1245, 1140, 1230, 0, 5000, 1120, 1235,
             "", "", "", "", "", ""],
        ]
        _write_gz_csv(os.path.join(d, "operations.csv.gz"), ops_header, ops_rows)

        # labs: subject 100 has preop cr 1.0 then postop cr 1.6 (>=1.5x -> AKI)
        # subject 101 has preop cr 0.8, postop 0.85 (no AKI)
        labs_header = ["subject_id", "chart_time", "item_name", "value"]
        labs_rows = [
            (100, 900, "creatinine", 1.0),     # preop (before anstart 1120)
            (100, 2000, "creatinine", 1.6),    # postop (after opend 1230)
            (101, 900, "creatinine", 0.8),
            (101, 2000, "creatinine", 0.85),
        ]
        _write_gz_csv(os.path.join(d, "labs.csv.gz"), labs_header, labs_rows)

        # diagnosis: subject 100 has HTN (I10) + DM (E11); 101 none
        dx_header = ["subject_id", "chart_time", "icd10_cm"]
        dx_rows = [(100, 0, "I10"), (100, 0, "E119"), (101, 0, "Z00")]
        _write_gz_csv(os.path.join(d, "diagnosis.csv.gz"), dx_header, dx_rows)

        # medications: subject 100 has norepinephrine ATC (secondary pressor source)
        med_header = ["subject_id", "chart_time", "route", "drug_name", "atc_code"]
        med_rows = [(100, 1150, "iv", "norepinephrine", "C01CA03")]
        _write_gz_csv(os.path.join(d, "medications.csv.gz"), med_header, med_rows)
        # NOTE: deliberately NO vitals.csv.gz -> PENDING-vitals path

    def test_build_pending_vitals(self):
        import math

        import pandas as pd
        with tempfile.TemporaryDirectory() as d:
            self._build_raw(d)
            out = os.path.join(d, "inspire_matrix.csv")
            cfg = {
                "kdigo": {"abs_rise_mgdl": 0.3, "abs_window_h": 48,
                          "rel_ratio": 1.5, "rel_window_h": 168},
                "organ_outcomes": {"postop_window_h": 168,
                                   "ULN": {"ast": 40.0, "alt": 40.0, "tbil": 1.2}},
            }
            summ = bm.build_inspire_matrix(d, out, cfg)

            self.assertEqual(summ["n_operations"], 2)
            self.assertEqual(summ["n_matrix_rows"], 2)
            self.assertTrue(summ["map_pending"])           # no vitals
            self.assertFalse(summ["vitals_available"])

            df = pd.read_csv(out)
            # required internal columns present
            for c in ["age", "sex_male", "asa_class", "baseline_cr", "egfr_ckd_epi",
                      "organ_renal", "composite", "preop_htn", "preop_dm",
                      "surgery_duration", "map_auc_below_65", "recovery_velocity",
                      "phe_vs_norepi", "any_vasopressor"]:
                self.assertIn(c, df.columns)

            # MAP columns empty (PENDING)
            self.assertTrue(df["map_auc_below_65"].isna().all())
            self.assertTrue(df["recovery_velocity"].isna().all())

            a = df[df["op_id"] == 400001].iloc[0]
            b = df[df["op_id"] == 400002].iloc[0]
            # subject 100: 1.0 -> 1.6 = 1.6x -> AKI=1
            self.assertEqual(int(a["organ_renal"]), 1)
            # subject 101: clean
            self.assertEqual(int(b["organ_renal"]), 0)
            # comorbidity flags
            self.assertEqual(int(a["preop_htn"]), 1)
            self.assertEqual(int(a["preop_dm"]), 1)
            self.assertEqual(int(b["preop_htn"]), 0)
            # surgery duration in MINUTES (opend-opstart = 90)
            self.assertAlmostEqual(float(a["surgery_duration"]), 90.0, places=3)
            # medications-ATC pressor fallback: subject 100 norepi -> phe_vs_norepi=0
            self.assertEqual(int(a["phe_vs_norepi"]), 0)
            self.assertEqual(int(a["any_vasopressor"]), 1)
            # baseline_cr / eGFR populated
            self.assertAlmostEqual(float(a["baseline_cr"]), 1.0, places=3)
            self.assertTrue(math.isfinite(float(a["egfr_ckd_epi"])))


if __name__ == "__main__":
    unittest.main(verbosity=2)
