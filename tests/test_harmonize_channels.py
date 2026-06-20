"""test_harmonize_channels.py -- stdlib-only tests for channel normalization.

Exercises `normalize_channel_names` and `plan_harmonization` (both pure
functions; no mne / numpy needed).
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.harmonize import normalize_channel_names, plan_harmonization
from pipeline.stream_fetch import RecordingRef


# ---------------------------------------------------------------------------
# Minimal config fixture -- mirrors base_cfg in test_integrity but uses the
# full clinical 19-channel set so all normalization edge cases can be exercised.
# ---------------------------------------------------------------------------

def _cfg_19ch():
    """Return a minimal config with the full 19-channel 10-20 target set."""
    return {
        "model": {
            "name": "CBraMod",
            "repo_id": "x",
            "revision": "r",
            "checkpoint_sha256": "TO-CONFIRM",
            "expected_sfreq_hz": 200,
            "channels_10_20": [
                "Fp1", "Fp2", "F3", "F4", "C3", "C4", "P3", "P4",
                "O1", "O2", "F7", "F8", "T3", "T4", "T5", "T6",
                "Fz", "Cz", "Pz",
            ],
            "window_seconds": 30,
            "window_stride_seconds": 30,
        },
        "harmonization": {
            "reference": "average",
            "notch_hz": [50, 60],
            "bandpass_hz": [0.5, 45],
            "artifact_rejection": "amplitude_zscore",
            "artifact_reject_z": 6.0,
        },
    }


def _ref():
    return RecordingRef("r", "p", "MGH")


# ---------------------------------------------------------------------------
# Helper: build a fully-decorated set of 19 clinical channel names
# (EEG prefix + modern names for T/P + -REF suffix) plus some non-EEG channels.
# ---------------------------------------------------------------------------

_CLINICAL_19 = [
    "EEG Fp1-REF", "EEG Fp2-REF",
    "EEG F3-REF",  "EEG F4-REF",
    "EEG C3-REF",  "EEG C4-REF",
    "EEG P3-REF",  "EEG P4-REF",
    "EEG O1-REF",  "EEG O2-REF",
    "EEG F7-REF",  "EEG F8-REF",
    "EEG T7-REF",  "EEG T8-REF",   # modern names -> T3 / T4
    "EEG P7-REF",  "EEG P8-REF",   # modern names -> T5 / T6
    "EEG Fz-REF",  "EEG Cz-REF",  "EEG Pz-REF",
    # non-EEG channels that should be ignored
    "ECG EKG",
    "EOG LOC",
    "A1",
    "A2",
    "EEG SpO2-REF",  # random clinical channel, not in 10-20
]


class TestNormalizeChannelNames(unittest.TestCase):
    """Unit tests for normalize_channel_names."""

    # --- basic prefix/suffix stripping ---

    def test_eeg_prefix_ref_suffix(self):
        result = normalize_channel_names(["EEG Fp1-REF"])
        self.assertEqual(result.get("Fp1"), "EEG Fp1-REF")

    def test_all_caps_no_decoration(self):
        result = normalize_channel_names(["FP1"])
        self.assertEqual(result.get("Fp1"), "FP1")

    def test_lowercase_with_trailing_space(self):
        result = normalize_channel_names(["fp1 "])
        self.assertEqual(result.get("Fp1"), "fp1 ")

    def test_le_suffix(self):
        result = normalize_channel_names(["C3-LE"])
        self.assertEqual(result.get("C3"), "C3-LE")

    def test_avg_suffix(self):
        result = normalize_channel_names(["F4-AVG"])
        self.assertEqual(result.get("F4"), "F4-AVG")

    def test_a1_suffix(self):
        result = normalize_channel_names(["O1-A1"])
        self.assertEqual(result.get("O1"), "O1-A1")

    def test_a2_suffix(self):
        result = normalize_channel_names(["O2-A2"])
        self.assertEqual(result.get("O2"), "O2-A2")

    def test_ref_suffix_no_dash(self):
        # Some systems append "REF" without a dash.
        result = normalize_channel_names(["Cz REF"])
        # After stripping outer space and "EEG " prefix: "Cz REF".
        # "REF" suffix (no dash) should be stripped.
        self.assertEqual(result.get("Cz"), "Cz REF")

    # --- modern <-> old 10-20 equivalences ---

    def test_t7_maps_to_t3(self):
        result = normalize_channel_names(["T7"])
        self.assertEqual(result.get("T3"), "T7")

    def test_t8_maps_to_t4(self):
        result = normalize_channel_names(["T8"])
        self.assertEqual(result.get("T4"), "T8")

    def test_p7_maps_to_t5(self):
        result = normalize_channel_names(["P7"])
        self.assertEqual(result.get("T5"), "P7")

    def test_p8_maps_to_t6(self):
        result = normalize_channel_names(["P8"])
        self.assertEqual(result.get("T6"), "P8")

    def test_modern_with_decoration(self):
        result = normalize_channel_names(["EEG T7-REF", "EEG P7-REF"])
        self.assertEqual(result.get("T3"), "EEG T7-REF")
        self.assertEqual(result.get("T5"), "EEG P7-REF")

    def test_old_names_still_accepted(self):
        result = normalize_channel_names(["T3", "T4", "T5", "T6"])
        self.assertEqual(result.get("T3"), "T3")
        self.assertEqual(result.get("T4"), "T4")
        self.assertEqual(result.get("T5"), "T5")
        self.assertEqual(result.get("T6"), "T6")

    # --- non-EEG channels are ignored ---

    def test_ecg_ignored(self):
        result = normalize_channel_names(["ECG EKG"])
        self.assertNotIn("ECG EKG", result.values())
        self.assertEqual(len(result), 0)

    def test_eog_ignored(self):
        result = normalize_channel_names(["EOG LOC", "EOG ROC"])
        self.assertEqual(len(result), 0)

    def test_a1_a2_ref_electrodes_ignored(self):
        result = normalize_channel_names(["A1", "A2"])
        # A1 and A2 are not in the canonical 10-20 target set
        self.assertEqual(len(result), 0)

    def test_unknown_channel_ignored(self):
        result = normalize_channel_names(["SpO2", "PHOTIC", "BURSTS"])
        self.assertEqual(len(result), 0)

    # --- first-occurrence wins ---

    def test_first_occurrence_wins_on_duplicate(self):
        result = normalize_channel_names(["Fp1", "EEG Fp1-REF", "FP1"])
        self.assertEqual(result.get("Fp1"), "Fp1")  # first occurrence

    # --- full clinical listing ---

    def test_clinical_19_resolves_all_canonical_channels(self):
        result = normalize_channel_names(_CLINICAL_19)
        canonical_targets = [
            "Fp1", "Fp2", "F3", "F4", "C3", "C4", "P3", "P4",
            "O1", "O2", "F7", "F8", "T3", "T4", "T5", "T6",
            "Fz", "Cz", "Pz",
        ]
        for ch in canonical_targets:
            self.assertIn(ch, result, msg=f"Missing canonical channel {ch!r}")
        # non-EEG names must not appear
        self.assertNotIn("ECG EKG", result.values())
        self.assertNotIn("EOG LOC", result.values())


class TestPlanHarmonizationWithNormalization(unittest.TestCase):
    """Integration tests: plan_harmonization + normalize_channel_names."""

    def test_clinical_19_is_now_mappable(self):
        """A recording using clinical naming conventions must be mappable."""
        cfg = _cfg_19ch()
        plan = plan_harmonization(cfg, _ref(), available_channels=_CLINICAL_19)
        self.assertTrue(plan.mappable,
                        msg=f"Expected mappable but dropped: {plan.dropped_channels}")

    def test_modern_names_make_recording_mappable(self):
        """T7/T8/P7/P8 (modern) cover T3/T4/T5/T6 in the plan."""
        cfg = _cfg_19ch()
        # Build a channel list that uses modern T/P names, plain (no prefix).
        modern_chans = [
            "Fp1", "Fp2", "F3", "F4", "C3", "C4", "P3", "P4",
            "O1", "O2", "F7", "F8",
            "T7", "T8",   # modern -> T3, T4
            "P7", "P8",   # modern -> T5, T6
            "Fz", "Cz", "Pz",
        ]
        plan = plan_harmonization(cfg, _ref(), available_channels=modern_chans)
        self.assertTrue(plan.mappable,
                        msg=f"Expected mappable but dropped: {plan.dropped_channels}")

    def test_rename_map_populated_for_non_canonical_names(self):
        """rename_map must include entries for channels needing a rename."""
        cfg = _cfg_19ch()
        plan = plan_harmonization(cfg, _ref(), available_channels=_CLINICAL_19)
        rename_dict = dict(plan.rename_map)  # original -> canonical
        # "EEG T7-REF" should be remapped to "T3"
        self.assertIn("EEG T7-REF", rename_dict)
        self.assertEqual(rename_dict["EEG T7-REF"], "T3")
        self.assertIn("EEG P7-REF", rename_dict)
        self.assertEqual(rename_dict["EEG P7-REF"], "T5")

    def test_rename_map_empty_when_no_renaming_needed(self):
        """If available channels already match the canonical names, rename_map
        should be empty (no unnecessary renames)."""
        cfg = _cfg_19ch()
        canonical_chans = list(cfg["model"]["channels_10_20"])
        plan = plan_harmonization(cfg, _ref(), available_channels=canonical_chans)
        self.assertTrue(plan.mappable)
        self.assertEqual(len(plan.rename_map), 0)

    def test_genuinely_missing_channel_is_not_mappable(self):
        """A recording truly lacking an electrode (e.g. no occipital leads)
        must remain NOT mappable after normalization."""
        cfg = _cfg_19ch()
        missing_occipital = [
            "EEG Fp1-REF", "EEG Fp2-REF",
            "EEG F3-REF",  "EEG F4-REF",
            "EEG C3-REF",  "EEG C4-REF",
            "EEG P3-REF",  "EEG P4-REF",
            # O1 and O2 deliberately omitted
            "EEG F7-REF",  "EEG F8-REF",
            "EEG T7-REF",  "EEG T8-REF",
            "EEG P7-REF",  "EEG P8-REF",
            "EEG Fz-REF",  "EEG Cz-REF",  "EEG Pz-REF",
        ]
        plan = plan_harmonization(cfg, _ref(), available_channels=missing_occipital)
        self.assertFalse(plan.mappable)
        self.assertIn("O1", plan.dropped_channels)
        self.assertIn("O2", plan.dropped_channels)

    def test_plan_hash_still_sensitive_to_params(self):
        """Adding rename entries must not break content_hash sensitivity."""
        cfg = _cfg_19ch()
        h1 = plan_harmonization(cfg, _ref(), _CLINICAL_19).content_hash()
        cfg["harmonization"]["notch_hz"] = [60]
        h2 = plan_harmonization(cfg, _ref(), _CLINICAL_19).content_hash()
        self.assertNotEqual(h1, h2)

    def test_no_channels_argument_leaves_dropped_empty(self):
        """Passing available_channels=None means eligibility is unknown;
        dropped_channels must be empty and mappable must be True."""
        cfg = _cfg_19ch()
        plan = plan_harmonization(cfg, _ref(), available_channels=None)
        self.assertEqual(plan.dropped_channels, ())
        self.assertTrue(plan.mappable)

    def test_original_strict_uppercase_matching_still_works(self):
        """Verify the pre-existing case-insensitive match still holds for
        channels that were already canonical (regression guard)."""
        # Use a 4-channel config (mirrors base_cfg in test_integrity).
        cfg = {
            "model": {
                "name": "CBraMod", "repo_id": "x", "revision": "r",
                "checkpoint_sha256": "TO-CONFIRM", "expected_sfreq_hz": 200,
                "channels_10_20": ["Fp1", "Fp2", "C3", "C4"],
                "window_seconds": 30, "window_stride_seconds": 30,
            },
            "harmonization": {
                "reference": "average", "notch_hz": [50, 60],
                "bandpass_hz": [0.5, 45], "artifact_rejection": "amplitude_zscore",
                "artifact_reject_z": 6.0,
            },
        }
        plan = plan_harmonization(cfg, _ref(), available_channels=["Fp1", "Fp2", "C3", "C4"])
        self.assertTrue(plan.mappable)
        plan2 = plan_harmonization(cfg, _ref(), available_channels=["Fp1", "Fp2"])
        self.assertFalse(plan2.mappable)
        self.assertEqual(set(plan2.dropped_channels), {"C3", "C4"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
