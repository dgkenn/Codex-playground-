"""test_risk_factors.py -- stdlib-only unit tests for vitaldb_aki/features/risk_factors.py.

Tests verify:
  1. Feature-spec contract: no postop timing, no duplicate names, correct set membership.
  2. preop_lab: picks most-recent value BEFORE anchor; never returns a postop value;
     respects the 30-day look-back window; handles missing/empty index gracefully.
  3. Comorbidity flags (ckd, liver, cardiac, infection) on synthetic case dicts.
  4. Surgical-descriptor encoding (open/general/position/high-risk) on synthetic dicts.
  5. extract() round-trip: correct keys emitted, None when labs_index absent.

Real-cohort coverage report (runs when invoked directly as __main__):
  python3 vitaldb_aki/tests/test_risk_factors.py --real
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from vitaldb_aki.features.base import audit_specs, LeakageError, FeatureSpec
from vitaldb_aki.features import risk_factors as rf


# ---------------------------------------------------------------------------
# Synthetic helpers
# ---------------------------------------------------------------------------

def _case(
    *,
    age: str = "55",
    sex: str = "M",
    preop_cr: str = "1.0",
    preop_ast: str = "20",
    preop_alt: str = "20",
    dx: str = "colon cancer",
    preop_ecg: str = "Normal Sinus Rhythm",
    approach: str = "Open",
    ane_type: str = "General",
    position: str = "Supine",
    optype: str = "Colorectal",
    opstart: str = "1000",
    opend: str = "10000",
) -> dict:
    return {
        "age": age, "sex": sex, "preop_cr": preop_cr,
        "preop_ast": preop_ast, "preop_alt": preop_alt,
        "dx": dx, "preop_ecg": preop_ecg,
        "approach": approach, "ane_type": ane_type,
        "position": position, "optype": optype,
        "opstart": opstart, "opend": opend,
    }


def _labs_index(entries: list[tuple[str, str, float, float]]) -> dict:
    """Build a mini labs_index from [(caseid, analyte, dt, val), ...]."""
    idx: dict = {}
    for cid, analyte, dt, val in entries:
        idx.setdefault(str(cid), {}).setdefault(analyte, []).append((dt, val))
    for by_analyte in idx.values():
        for lst in by_analyte.values():
            lst.sort(key=lambda x: x[0])
    return idx


# ---------------------------------------------------------------------------
# Spec / contract tests
# ---------------------------------------------------------------------------

class TestSpecContract(unittest.TestCase):
    def test_specs_pass_leakage_audit(self):
        audit_specs(rf.SPECS)

    def test_no_postop_timing(self):
        for s in rf.SPECS:
            self.assertIn(s.timing, ("preop", "intraop"),
                          f"{s.name} has forbidden timing {s.timing!r}")

    def test_all_comprehensive(self):
        for s in rf.SPECS:
            self.assertEqual(s.fset, "comprehensive", s.name)

    def test_no_duplicate_names(self):
        names = [s.name for s in rf.SPECS]
        self.assertEqual(len(names), len(set(names)))

    def test_expected_feature_names_present(self):
        names = {s.name for s in rf.SPECS}
        required = {
            "preop_crp", "preop_lactate", "preop_chloride",
            "preop_wbc", "preop_hct", "preop_gfr_lab",
            "ckd_flag", "liver_disease_flag", "cardiac_flag", "infection_flag",
            "is_open_surgery", "is_general_anesthesia",
            "position_risk", "is_high_risk_surgery",
        }
        self.assertTrue(required.issubset(names), names - required)

    def test_postop_spec_raises_leakage(self):
        """Confirm the leakage firewall is active (meta-test)."""
        with self.assertRaises(LeakageError):
            audit_specs([FeatureSpec("icu_stay", "comprehensive", "postop")])


# ---------------------------------------------------------------------------
# preop_lab tests
# ---------------------------------------------------------------------------

class TestPreopLab(unittest.TestCase):
    """Tests for the preop_lab helper."""

    def test_picks_most_recent_preop_value(self):
        # anchor=10000, window=30d. dt=9000 is more recent than dt=5000.
        idx = _labs_index([
            ("1", "crp", 5000.0, 3.0),
            ("1", "crp", 9000.0, 7.0),  # most recent before anchor
        ])
        val = rf.preop_lab(idx, "1", "crp", anchor_s=10000.0)
        self.assertEqual(val, 7.0)

    def test_never_returns_postop_value(self):
        # Only value is at dt=10000 == anchor -> must be excluded (postop)
        idx = _labs_index([("2", "crp", 10000.0, 99.0)])
        val = rf.preop_lab(idx, "2", "crp", anchor_s=10000.0)
        self.assertIsNone(val)

    def test_never_returns_value_after_anchor(self):
        # dt > anchor -> excluded
        idx = _labs_index([("3", "crp", 12000.0, 15.0)])
        val = rf.preop_lab(idx, "3", "crp", anchor_s=10000.0)
        self.assertIsNone(val)

    def test_postop_value_ignored_preop_value_returned(self):
        # Mix of preop and postop; postop must be skipped
        idx = _labs_index([
            ("4", "crp", 9000.0, 5.0),   # preop (dt < anchor=10000)
            ("4", "crp", 11000.0, 20.0), # postop -> must be ignored
        ])
        val = rf.preop_lab(idx, "4", "crp", anchor_s=10000.0)
        self.assertEqual(val, 5.0)

    def test_respects_window_lower_bound(self):
        # window = 5000s; anchor=10000; lo=5000. dt=4999 is out-of-window.
        idx = _labs_index([
            ("5", "crp", 4999.0, 1.0),  # too old
            ("5", "crp", 5001.0, 2.0),  # within window
        ])
        val = rf.preop_lab(idx, "5", "crp", anchor_s=10000.0, window_s=5000.0)
        self.assertEqual(val, 2.0)

    def test_all_values_too_old_returns_none(self):
        idx = _labs_index([("6", "crp", 1.0, 5.0)])
        val = rf.preop_lab(idx, "6", "crp", anchor_s=10000.0, window_s=100.0)
        self.assertIsNone(val)

    def test_missing_caseid_returns_none(self):
        idx = _labs_index([("7", "crp", 5000.0, 5.0)])
        self.assertIsNone(rf.preop_lab(idx, "999", "crp", anchor_s=10000.0))

    def test_missing_analyte_returns_none(self):
        idx = _labs_index([("8", "crp", 5000.0, 5.0)])
        self.assertIsNone(rf.preop_lab(idx, "8", "wbc", anchor_s=10000.0))

    def test_empty_index_returns_none(self):
        self.assertIsNone(rf.preop_lab({}, "1", "crp", anchor_s=10000.0))

    def test_negative_dt_preop_lab_accepted(self):
        # Negative dt = before casestart (pre-admission) -- clearly preop
        idx = _labs_index([("9", "crp", -50000.0, 4.2)])
        val = rf.preop_lab(idx, "9", "crp", anchor_s=10000.0)
        self.assertAlmostEqual(val, 4.2)


# ---------------------------------------------------------------------------
# CKD flag
# ---------------------------------------------------------------------------

class TestCKDFlag(unittest.TestCase):
    def test_egfr_below_60_flagged(self):
        # 80yo male, high creatinine -> eGFR well below 60
        c = _case(age="80", sex="M", preop_cr="2.5")
        self.assertEqual(rf._ckd_flag(c), 1)

    def test_egfr_above_60_not_flagged(self):
        # Young healthy male, Scr 0.9
        c = _case(age="40", sex="M", preop_cr="0.9")
        self.assertEqual(rf._ckd_flag(c), 0)

    def test_missing_cr_returns_none(self):
        c = _case(preop_cr="")
        self.assertIsNone(rf._ckd_flag(c))

    def test_female_lower_egfr_boundary(self):
        # 75yo female, Scr=1.4 -> eGFR around 36 (<60) -> CKD
        c = _case(age="75", sex="F", preop_cr="1.4")
        self.assertEqual(rf._ckd_flag(c), 1)


# ---------------------------------------------------------------------------
# Liver disease flag
# ---------------------------------------------------------------------------

class TestLiverFlag(unittest.TestCase):
    def test_cirrhosis_dx_flagged(self):
        c = _case(dx="liver cirrhosis child-pugh a")
        self.assertEqual(rf._liver_flag(c), 1)

    def test_hepatic_failure_dx_flagged(self):
        c = _case(dx="hepatic failure with coma")
        self.assertEqual(rf._liver_flag(c), 1)

    def test_hcc_dx_flagged(self):
        c = _case(dx="hepatocellular carcinoma")
        self.assertEqual(rf._liver_flag(c), 1)

    def test_liver_donor_flagged(self):
        c = _case(dx="liver donor")
        self.assertEqual(rf._liver_flag(c), 1)

    def test_normal_dx_not_flagged(self):
        c = _case(dx="colon cancer", preop_ast="20", preop_alt="20")
        self.assertEqual(rf._liver_flag(c), 0)

    def test_ast_above_80_flagged(self):
        c = _case(dx="colon cancer", preop_ast="120", preop_alt="30")
        self.assertEqual(rf._liver_flag(c), 1)

    def test_alt_above_80_flagged(self):
        c = _case(dx="colon cancer", preop_ast="30", preop_alt="150")
        self.assertEqual(rf._liver_flag(c), 1)

    def test_enzymes_at_80_not_flagged(self):
        # exactly 80 is not ABOVE 80
        c = _case(dx="colon cancer", preop_ast="80", preop_alt="80")
        self.assertEqual(rf._liver_flag(c), 0)

    def test_missing_ast_alt_dx_normal_not_flagged(self):
        c = _case(dx="breast cancer", preop_ast="", preop_alt="")
        self.assertEqual(rf._liver_flag(c), 0)


# ---------------------------------------------------------------------------
# Cardiac flag
# ---------------------------------------------------------------------------

class TestCardiacFlag(unittest.TestCase):
    def test_normal_ecg_no_flag(self):
        c = _case(preop_ecg="Normal Sinus Rhythm", dx="colon cancer")
        self.assertEqual(rf._cardiac_flag(c), 0)

    def test_afib_flagged(self):
        c = _case(preop_ecg="Atrial fibrillation")
        self.assertEqual(rf._cardiac_flag(c), 1)

    def test_bundle_branch_block_flagged(self):
        c = _case(preop_ecg="Right bundle branch block")
        self.assertEqual(rf._cardiac_flag(c), 1)

    def test_pacemaker_flagged(self):
        c = _case(preop_ecg="Electronic ventricular pacemaker")
        self.assertEqual(rf._cardiac_flag(c), 1)

    def test_av_block_flagged(self):
        c = _case(preop_ecg="1st degree A-V block")
        self.assertEqual(rf._cardiac_flag(c), 1)

    def test_chf_in_dx_flagged(self):
        c = _case(preop_ecg="Normal Sinus Rhythm",
                  dx="congestive heart failure, diastolic")
        self.assertEqual(rf._cardiac_flag(c), 1)

    def test_cardiomyopathy_in_dx_flagged(self):
        c = _case(preop_ecg="Normal Sinus Rhythm", dx="dilated cardiomyopathy")
        self.assertEqual(rf._cardiac_flag(c), 1)

    def test_empty_ecg_no_crash(self):
        c = _case(preop_ecg="", dx="colon cancer")
        self.assertEqual(rf._cardiac_flag(c), 0)


# ---------------------------------------------------------------------------
# Infection flag
# ---------------------------------------------------------------------------

class TestInfectionFlag(unittest.TestCase):
    def test_sepsis_dx_flagged(self):
        c = _case(dx="septic shock")
        self.assertEqual(rf._infection_flag(c), 1)

    def test_abscess_flagged(self):
        c = _case(dx="abdominopelvic abscess")
        self.assertEqual(rf._infection_flag(c), 1)

    def test_peritonitis_flagged(self):
        c = _case(dx="acute peritonitis")
        self.assertEqual(rf._infection_flag(c), 1)

    def test_bacteremia_flagged(self):
        c = _case(dx="bacteremia")
        self.assertEqual(rf._infection_flag(c), 1)

    def test_normal_dx_not_flagged(self):
        c = _case(dx="rectal cancer")
        self.assertEqual(rf._infection_flag(c), 0)

    def test_wound_infection_flagged(self):
        c = _case(dx="surgical wound infection")
        self.assertEqual(rf._infection_flag(c), 1)


# ---------------------------------------------------------------------------
# Surgical descriptor tests
# ---------------------------------------------------------------------------

class TestSurgicalDescriptors(unittest.TestCase):
    def test_open_surgery(self):
        self.assertEqual(rf._is_open(_case(approach="Open")), 1)
        self.assertEqual(rf._is_open(_case(approach="Videoscopic")), 0)
        self.assertEqual(rf._is_open(_case(approach="Robotic")), 0)

    def test_general_anesthesia(self):
        self.assertEqual(rf._is_general(_case(ane_type="General")), 1)
        self.assertEqual(rf._is_general(_case(ane_type="Spinal")), 0)
        self.assertEqual(rf._is_general(_case(ane_type="Sedationalgesia")), 0)

    def test_position_risk_supine_zero(self):
        self.assertEqual(rf._position_risk(_case(position="Supine")), 0)

    def test_position_risk_lithotomy_one(self):
        self.assertEqual(rf._position_risk(_case(position="Lithotomy")), 1)

    def test_position_risk_lateral_one(self):
        self.assertEqual(rf._position_risk(_case(position="Left lateral decubitus")), 1)

    def test_position_risk_prone_two(self):
        self.assertEqual(rf._position_risk(_case(position="Prone")), 2)

    def test_position_risk_reverse_trendelenburg_two(self):
        self.assertEqual(rf._position_risk(_case(position="Reverse Trendelenburg")), 2)

    def test_position_risk_kidney_three(self):
        self.assertEqual(rf._position_risk(_case(position="Right kidney")), 3)

    def test_position_risk_sitting_three(self):
        self.assertEqual(rf._position_risk(_case(position="Sitting")), 3)

    def test_position_risk_unknown_zero(self):
        self.assertEqual(rf._position_risk(_case(position="")), 0)
        self.assertEqual(rf._position_risk(_case(position="Unknown")), 0)

    def test_high_risk_optype(self):
        for ot in ("Hepatic", "Vascular", "Biliary/Pancreas", "Major resection",
                   "Colorectal", "Stomach", "Transplantation"):
            self.assertEqual(rf._is_high_risk(_case(optype=ot)), 1, ot)

    def test_non_high_risk_optype(self):
        for ot in ("Breast", "Thyroid", "Minor resection", "Others"):
            self.assertEqual(rf._is_high_risk(_case(optype=ot)), 0, ot)


# ---------------------------------------------------------------------------
# build_labs_index
# ---------------------------------------------------------------------------

class TestBuildLabsIndex(unittest.TestCase):
    def test_filters_to_target_analytes(self):
        rows = [
            {"caseid": "1", "dt": "1000", "name": "crp",   "result": "5.0"},
            {"caseid": "1", "dt": "2000", "name": "glucose","result": "100"},  # ignored
            {"caseid": "1", "dt": "3000", "name": "lac",   "result": "2.1"},
        ]
        idx = rf.build_labs_index(rows)
        self.assertIn("crp", idx["1"])
        self.assertIn("lac", idx["1"])
        self.assertNotIn("glucose", idx["1"])

    def test_non_numeric_result_skipped(self):
        rows = [
            {"caseid": "2", "dt": "1000", "name": "crp", "result": "N/A"},
            {"caseid": "2", "dt": "2000", "name": "crp", "result": "3.5"},
        ]
        idx = rf.build_labs_index(rows)
        self.assertEqual(len(idx["2"]["crp"]), 1)
        self.assertAlmostEqual(idx["2"]["crp"][0][1], 3.5)

    def test_sorted_ascending(self):
        rows = [
            {"caseid": "3", "dt": "5000", "name": "crp", "result": "2.0"},
            {"caseid": "3", "dt": "1000", "name": "crp", "result": "1.0"},
        ]
        idx = rf.build_labs_index(rows)
        dts = [t for t, _ in idx["3"]["crp"]]
        self.assertEqual(dts, sorted(dts))


# ---------------------------------------------------------------------------
# extract() round-trip
# ---------------------------------------------------------------------------

class TestExtract(unittest.TestCase):
    def _minimal_case(self) -> dict:
        return _case(
            age="55", sex="M", preop_cr="1.2",
            preop_ast="30", preop_alt="25",
            dx="rectal cancer",
            preop_ecg="Normal Sinus Rhythm",
            approach="Open", ane_type="General",
            position="Lithotomy", optype="Colorectal",
            opend="10000",
        )

    def test_all_expected_keys_present(self):
        cases = {"1": self._minimal_case()}
        result = rf.extract({}, cases, ["1"])
        row = result["1"]
        for s in rf.SPECS:
            self.assertIn(s.name, row, f"missing key {s.name!r}")

    def test_lab_features_none_without_labs_index(self):
        cases = {"1": self._minimal_case()}
        result = rf.extract({}, cases, ["1"])  # no labs_index
        row = result["1"]
        for name in ("preop_crp", "preop_lactate", "preop_chloride",
                     "preop_wbc", "preop_hct", "preop_gfr_lab"):
            self.assertIsNone(row[name], f"{name} should be None without labs_index")

    def test_lab_features_populated_with_labs_index(self):
        c = self._minimal_case()
        # anchor = opend = 10000
        labs = [
            {"caseid": "1", "dt": "9500",  "name": "crp", "result": "8.5"},
            {"caseid": "1", "dt": "9000",  "name": "lac", "result": "1.8"},
            {"caseid": "1", "dt": "9800",  "name": "cl",  "result": "103"},
            {"caseid": "1", "dt": "9700",  "name": "wbc", "result": "7.2"},
            {"caseid": "1", "dt": "9600",  "name": "hct", "result": "36.5"},
            {"caseid": "1", "dt": "9400",  "name": "gfr", "result": "72.0"},
            # postop value -- must NOT appear
            {"caseid": "1", "dt": "11000", "name": "crp", "result": "50.0"},
        ]
        idx = rf.build_labs_index(labs)
        result = rf.extract({}, {"1": c}, ["1"], labs_index=idx)
        row = result["1"]
        self.assertAlmostEqual(row["preop_crp"],      8.5)
        self.assertAlmostEqual(row["preop_lactate"],  1.8)
        self.assertAlmostEqual(row["preop_chloride"], 103.0)
        self.assertAlmostEqual(row["preop_wbc"],      7.2)
        self.assertAlmostEqual(row["preop_hct"],      36.5)
        self.assertAlmostEqual(row["preop_gfr_lab"],  72.0)

    def test_comorbidity_flags_correct(self):
        c = _case(
            dx="liver cirrhosis",
            preop_ecg="Atrial fibrillation",
            approach="Videoscopic",
            ane_type="Spinal",
            position="Prone",
            optype="Vascular",
        )
        result = rf.extract({}, {"10": c}, ["10"])
        row = result["10"]
        self.assertEqual(row["liver_disease_flag"], 1)
        self.assertEqual(row["cardiac_flag"], 1)
        self.assertEqual(row["is_open_surgery"], 0)
        self.assertEqual(row["is_general_anesthesia"], 0)
        self.assertEqual(row["position_risk"], 2)
        self.assertEqual(row["is_high_risk_surgery"], 1)

    def test_missing_caseid_skipped(self):
        result = rf.extract({}, {}, ["999"])
        self.assertNotIn("999", result)


# ---------------------------------------------------------------------------
# Real-cohort coverage report (only runs as __main__ with --real flag)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if "--real" in sys.argv:
        import csv
        import os

        BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        CACHE = os.path.join(BASE, "cache")

        print("Loading cohort...")
        with open(os.path.join(CACHE, "cohort.csv"), newline="") as fh:
            cohort = list(csv.DictReader(fh))
        caseids = [r["caseid"] for r in cohort]
        N = len(caseids)
        print(f"  Cohort size: {N}")

        print("Loading /cases...")
        with open(os.path.join(CACHE, "cases.csv"), newline="", encoding="utf-8-sig") as fh:
            cases_list = list(csv.DictReader(fh))
        cases_by_id = {c["caseid"]: c for c in cases_list}

        print("Loading /labs and building index...")
        with open(os.path.join(CACHE, "labs.csv"), newline="") as fh:
            labs_rows = list(csv.DictReader(fh))
        labs_index = rf.build_labs_index(labs_rows)
        print(f"  Labs rows: {len(labs_rows)}")

        print("Extracting features...")
        result = rf.extract({}, cases_by_id, caseids, labs_index=labs_index)

        print(f"\nPer-feature coverage % (N={N})")
        print(f"{'Feature':<26} {'Non-missing':>11}  {'Coverage %':>10}")
        print("-" * 52)
        for s in rf.SPECS:
            n_present = sum(1 for cid in caseids
                            if result.get(cid, {}).get(s.name) is not None)
            pct = 100.0 * n_present / N
            print(f"  {s.name:<24} {n_present:>9}/{N}  {pct:>8.1f}%")

        sys.exit(0)

    unittest.main(verbosity=2)
