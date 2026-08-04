"""tests/test_heedb_age_join.py -- patients-CSV join tests for HEEDBBDSPClient.

Verifies that:
  1. RecordingRefs get age + sex from HEEDB_patients.csv even when the
     per-site eeg-metadata catalog has empty AgeAtVisit / SexDSC columns.
  2. A patient with age 15 is filtered out by iter_qualifying_recordings
     (adults-only, min_age=18).
  3. A patient with age 40 passes the age filter.
  4. A patient with no entry in patients.csv gets age=None (kept, since
     age-None is not filtered out).

No network, no credentials, no scientific stack required (stdlib only).
"""
from __future__ import annotations

import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from guards.heldout_guard import HeldoutGuard
from pipeline.stream_fetch import HEEDBBDSPClient, RecordingRef, iter_qualifying_recordings


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SITE = "S0001"
_PATIENTS_KEY = "EEG/HEEDB_Metadata/HEEDB_patients.csv"
_CATALOG_KEY = "EEG/eeg-metadata/S0001_eeg_metadata_test.csv"

# Catalog CSV: AgeAtVisit and SexDSC are intentionally empty for all rows
# to simulate the real HEEDB situation where these columns are largely blank.
_CATALOG_CSV = (
    "SiteID,BDSPPatientID,BidsFolder,SessionID,CreationTime,StartTime,EndTime,"
    "DurationInSeconds,EEGFolder,ServiceName,HasXLTEKAnnotations,HasPersystAnnotations,"
    "AgeAtVisit,DateOfDeath,SexDSC,BidsFlag\n"
    # patient ALPHA: will be joined -> age=40, sex=F  (adult, should pass)
    "S0001,111200001,sub-S0001111200001,SES001,2021-01-01,,,"
    "600.0,eeg_folder,Routine,0,0,,,, 1\n"
    # patient BETA: will be joined -> age=15, sex=M  (minor, should be filtered)
    "S0001,111200002,sub-S0001111200002,SES002,2021-01-02,,,"
    "600.0,eeg_folder,Routine,0,0,,,, 1\n"
    # patient GAMMA: NOT in patients.csv -> age=None, sex=None  (kept; None not filtered)
    "S0001,111200003,sub-S0001111200003,SES003,2021-01-03,,,"
    "600.0,eeg_folder,Routine,0,0,,,, 1\n"
)

# patients CSV: supplies demographics for ALPHA and BETA only (GAMMA is absent)
_PATIENTS_CSV = (
    "SiteID,BDSPPatientID,Sex,AgeAtVisitAvg,RaceAndEthnicity,ICD10Count,MedicationCount\n"
    "S0001,111200001,F,40.0,Unknown,3,5\n"
    "S0001,111200002,M,15.0,Unknown,1,0\n"
)

# EDF keys resolvable for all three sessions
_EDF_KEYS = {
    "EEG/bids/S0001/sub-S0001111200001/ses-SES001/eeg/": [
        "EEG/bids/S0001/sub-S0001111200001/ses-SES001/eeg/"
        "sub-S0001111200001_ses-SES001_task-Routine_eeg.edf"
    ],
    "EEG/bids/S0001/sub-S0001111200002/ses-SES002/eeg/": [
        "EEG/bids/S0001/sub-S0001111200002/ses-SES002/eeg/"
        "sub-S0001111200002_ses-SES002_task-Routine_eeg.edf"
    ],
    "EEG/bids/S0001/sub-S0001111200003/ses-SES003/eeg/": [
        "EEG/bids/S0001/sub-S0001111200003/ses-SES003/eeg/"
        "sub-S0001111200003_ses-SES003_task-Routine_eeg.edf"
    ],
}


# ---------------------------------------------------------------------------
# Fake S3
# ---------------------------------------------------------------------------

class _FakeBody:
    def __init__(self, data: bytes):
        self._b = io.BytesIO(data)

    def read(self) -> bytes:
        return self._b.read()


class _FakeS3:
    """Routes get_object to catalog CSV or patients CSV by key."""

    def __init__(self):
        self._catalog = _CATALOG_CSV.encode("utf-8")
        self._patients = _PATIENTS_CSV.encode("utf-8")

    def list_objects_v2(self, Bucket, Prefix, **_):  # noqa: N803
        # Catalog discovery listing
        if Prefix.endswith("S0001_"):
            return {"Contents": [{"Key": _CATALOG_KEY}]}
        # EEG folder listing for EDF key resolution
        contents = [{"Key": k} for k in _EDF_KEYS.get(Prefix, [])]
        return {"Contents": contents}

    def get_object(self, Bucket, Key, **_):  # noqa: N803
        if Key == _PATIENTS_KEY:
            return {"Body": _FakeBody(self._patients)}
        return {"Body": _FakeBody(self._catalog)}


# ---------------------------------------------------------------------------
# Config + helpers
# ---------------------------------------------------------------------------

def _cfg():
    return {
        "phase": 1,
        "cohort": {"primary_min_age_years": 18},
        "sites": {"discovery": [_SITE], "held_out": "S0099"},
        "log_dir": "/tmp/heedb_age_join_test_logs",
        "data": {
            "source": "HEEDB_BDSP",
            "scratch_dir": "/tmp/heedb_scratch",
            "heedb": {
                "access_point": "arn:aws:s3:us-east-1:000000000000:accesspoint/test-ap",
                "region": "us-east-1",
                "profile": None,
                "metadata_prefix": "EEG/eeg-metadata/",
                "bids_prefix": "EEG/bids/",
                "max_duration_s": 1200,
                "tasks": ["Routine"],
                # explicitly set (also tests the config key path)
                "patients_key": _PATIENTS_KEY,
            },
        },
    }


def _make_client() -> HEEDBBDSPClient:
    return HEEDBBDSPClient(_cfg(), s3=_FakeS3())


def _guard(cfg) -> HeldoutGuard:
    return HeldoutGuard(cfg)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPatientsJoinPopulatesAge(unittest.TestCase):
    """age + sex come from patients CSV even when catalog columns are empty."""

    def setUp(self):
        self.client = _make_client()
        self.refs: list[RecordingRef] = list(self.client.list_recordings(_SITE))

    def test_all_three_recordings_returned(self):
        self.assertEqual(len(self.refs), 3)

    def _ref(self, tag: str) -> RecordingRef:
        return next(r for r in self.refs if tag in r.recording_id)

    def test_alpha_age_from_patients_csv(self):
        """ALPHA: catalog has no AgeAtVisit; patients CSV supplies 40.0."""
        ref = self._ref("111200001")
        self.assertAlmostEqual(ref.age, 40.0)

    def test_alpha_sex_from_patients_csv(self):
        """ALPHA: catalog has no SexDSC; patients CSV supplies 'F'."""
        ref = self._ref("111200001")
        self.assertEqual(ref.sex, "F")

    def test_beta_age_from_patients_csv(self):
        """BETA: catalog has no AgeAtVisit; patients CSV supplies 15.0."""
        ref = self._ref("111200002")
        self.assertAlmostEqual(ref.age, 15.0)

    def test_beta_sex_from_patients_csv(self):
        """BETA: catalog has no SexDSC; patients CSV supplies 'M'."""
        ref = self._ref("111200002")
        self.assertEqual(ref.sex, "M")

    def test_gamma_age_none_when_not_in_patients(self):
        """GAMMA: absent from patients.csv -> age is None (fall back, still None)."""
        ref = self._ref("111200003")
        self.assertIsNone(ref.age)

    def test_gamma_sex_none_when_not_in_patients(self):
        """GAMMA: absent from patients.csv -> sex is None."""
        ref = self._ref("111200003")
        self.assertIsNone(ref.sex)


class TestAgeFilterWithPatientsJoin(unittest.TestCase):
    """iter_qualifying_recordings applies adults-only filter after the join."""

    def setUp(self):
        cfg = _cfg()
        guard = _guard(cfg)
        client = _make_client()
        self.qualifying: list[RecordingRef] = list(
            iter_qualifying_recordings(cfg, guard, client=client)
        )

    def test_minor_filtered_out(self):
        """BETA (age=15) must not appear in qualifying recordings."""
        recording_ids = [r.recording_id for r in self.qualifying]
        self.assertFalse(any("111200002" in rid for rid in recording_ids))

    def test_adult_passes(self):
        """ALPHA (age=40) must appear in qualifying recordings."""
        recording_ids = [r.recording_id for r in self.qualifying]
        self.assertTrue(any("111200001" in rid for rid in recording_ids))

    def test_unknown_age_passes(self):
        """GAMMA (age=None) must appear -- unknown age is not filtered out."""
        recording_ids = [r.recording_id for r in self.qualifying]
        self.assertTrue(any("111200003" in rid for rid in recording_ids))

    def test_exactly_two_qualifying(self):
        """Only ALPHA (age=40) and GAMMA (age=None) qualify; BETA (age=15) is excluded."""
        self.assertEqual(len(self.qualifying), 2)


class TestPatientsKeyConfig(unittest.TestCase):
    """Config key cfg['data']['heedb']['patients_key'] controls the S3 path."""

    def test_default_patients_key(self):
        """When patients_key is absent from config, default path is used."""
        cfg = _cfg()
        del cfg["data"]["heedb"]["patients_key"]
        client = HEEDBBDSPClient(cfg, s3=_FakeS3())
        self.assertEqual(client._patients_key, "EEG/HEEDB_Metadata/HEEDB_patients.csv")

    def test_custom_patients_key(self):
        """An explicit patients_key overrides the default."""
        cfg = _cfg()
        cfg["data"]["heedb"]["patients_key"] = "EEG/HEEDB_Metadata/custom_patients.csv"
        client = HEEDBBDSPClient(cfg, s3=_FakeS3())
        self.assertEqual(client._patients_key, "EEG/HEEDB_Metadata/custom_patients.csv")

    def test_patients_csv_loaded_once(self):
        """_load_patients is only called once (caching)."""
        client = _make_client()
        _ = client._load_patients()
        first = client._patients
        _ = client._load_patients()
        self.assertIs(client._patients, first)


if __name__ == "__main__":
    unittest.main(verbosity=2)
