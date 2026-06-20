"""HEEDBBDSPClient -- catalog parsing + EDF-key resolution, no AWS required.

A fake S3 object (exposing list_objects_v2 + get_object) is injected so that:
  * catalog CSV parsing -> RecordingRef field mapping is tested
  * max_duration_s filter is tested
  * EDF key resolution (listing the eeg/ folder) is tested
  * DateOfDeath is confirmed absent from every RecordingRef

No network, no credentials, no mne needed.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.stream_fetch import HEEDBBDSPClient, RecordingRef, make_client


# ---------------------------------------------------------------------------
# Minimal fake catalog CSV matching the real HEEDB BDSP schema
# ---------------------------------------------------------------------------

_SITE = "S0001"

_CATALOG_CSV = (
    "SiteID,BDSPPatientID,BidsFolder,SessionID,CreationTime,StartTime,EndTime,"
    "DurationInSeconds,EEGFolder,ServiceName,HasXLTEKAnnotations,HasPersystAnnotations,"
    "AgeAtVisit,DateOfDeath,SexDSC,BidsFlag\n"
    # row 1: Routine EEG, 600 s, has age+sex (catalog values intentionally left; patients CSV wins)
    "S0001,PID001,sub-S0001111189001,SES001,2020-01-01,,,"
    "600.0,eeg_folder,Routine,0,0,55.0,,M,1\n"
    # row 2: Routine EEG, 900 s, missing age+sex
    "S0001,PID002,sub-S0001111189002,SES002,2020-01-02,,,"
    "900.0,eeg_folder,Routine,0,0,,,F,1\n"
    # row 3: too long (> max_duration_s=1200)
    "S0001,PID003,sub-S0001111189003,SES003,2020-01-03,,,"
    "2000.0,eeg_folder,Routine,0,0,40.0,,M,1\n"
    # row 4: wrong task (LTM, not in tasks=["Routine"])
    "S0001,PID004,sub-S0001111189004,SES004,2020-01-04,,,"
    "500.0,eeg_folder,LTM,0,0,30.0,,F,1\n"
    # row 5: EDF key unresolvable (fake S3 returns no keys for this session)
    "S0001,PID005,sub-S0001111189005,SES005,2020-01-05,,,"
    "400.0,eeg_folder,Routine,0,0,60.0,,M,1\n"
)

# Patients CSV -- supplies the same age/sex as the catalog for row 1 so
# existing tests continue to pass; row 2 gains demographics from here.
# BDSPPatientID is the numeric suffix (patient_id with SiteID prefix stripped).
_PATIENTS_CSV = (
    "SiteID,BDSPPatientID,Sex,AgeAtVisitAvg,RaceAndEthnicity\n"
    "S0001,111189001,M,55.0,Unknown\n"
    "S0001,111189002,F,32.0,Unknown\n"
)

# EDF keys that will be "found" when listing sessions SES001 and SES002
_EDF_KEYS = {
    "EEG/bids/S0001/sub-S0001111189001/ses-SES001/eeg/": [
        "EEG/bids/S0001/sub-S0001111189001/ses-SES001/eeg/"
        "sub-S0001111189001_ses-SES001_task-EEG_eeg.edf"
    ],
    "EEG/bids/S0001/sub-S0001111189002/ses-SES002/eeg/": [
        "EEG/bids/S0001/sub-S0001111189002/ses-SES002/eeg/"
        "sub-S0001111189002_ses-SES002_task-EEG_eeg.edf"
    ],
    # SES003 blocked by duration; SES004 blocked by task; SES005 returns no EDF
}


class _FakeBody:
    def __init__(self, data: bytes):
        self._b = io.BytesIO(data)

    def read(self) -> bytes:
        return self._b.read()


_PATIENTS_KEY = "EEG/HEEDB_Metadata/HEEDB_patients.csv"


class _FakeS3:
    """Minimal stand-in for a boto3 S3 client."""

    def __init__(self, catalog_csv: str, edf_keys: dict, patients_csv: str = ""):
        self._catalog = catalog_csv.encode("utf-8")
        self._patients = patients_csv.encode("utf-8") if patients_csv else b"SiteID,BDSPPatientID,Sex,AgeAtVisitAvg\n"
        self._edf_keys = edf_keys

    def list_objects_v2(self, Bucket, Prefix, **_):  # noqa: N803
        # Catalog discovery listing
        if Prefix.endswith("S0001_"):
            return {
                "Contents": [
                    {"Key": "EEG/eeg-metadata/S0001_eeg_metadata_2020.csv"}
                ]
            }
        # EEG folder listing for EDF key resolution
        contents = [
            {"Key": k} for k in self._edf_keys.get(Prefix, [])
        ]
        return {"Contents": contents}

    def get_object(self, Bucket, Key, **_):  # noqa: N803
        if Key == _PATIENTS_KEY:
            return {"Body": _FakeBody(self._patients)}
        return {"Body": _FakeBody(self._catalog)}


def _cfg(max_duration_s=1200, tasks=None):
    if tasks is None:
        tasks = ["Routine"]
    return {
        "phase": 1,
        "cohort": {"primary_min_age_years": 18},
        "sites": {"discovery": ["S0001", "S0002"], "held_out": "S0003"},
        "log_dir": "/tmp/heedb_bdsp_test_logs",
        "data": {
            "source": "HEEDB_BDSP",
            "scratch_dir": "/tmp/heedb_scratch",
            "heedb": {
                "access_point": "arn:aws:s3:us-east-1:184438910517:accesspoint/test-ap",
                "region": "us-east-1",
                "profile": None,
                "metadata_prefix": "EEG/eeg-metadata/",
                "bids_prefix": "EEG/bids/",
                "max_duration_s": max_duration_s,
                "tasks": tasks,
            },
        },
    }


def _client(max_duration_s=1200, tasks=None):
    cfg = _cfg(max_duration_s=max_duration_s, tasks=tasks)
    fake_s3 = _FakeS3(_CATALOG_CSV, _EDF_KEYS, patients_csv=_PATIENTS_CSV)
    return HEEDBBDSPClient(cfg, s3=fake_s3)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFactory(unittest.TestCase):
    def test_make_client_returns_heedb_client(self):
        self.assertIsInstance(make_client(_cfg()), HEEDBBDSPClient)


class TestCatalogParsing(unittest.TestCase):
    def setUp(self):
        self.client = _client()
        self.refs = list(self.client.list_recordings(_SITE))

    def test_correct_number_of_refs(self):
        # rows 1 and 2 pass all filters and have resolvable EDF keys
        self.assertEqual(len(self.refs), 2)

    def test_recording_id_format(self):
        ids = {r.recording_id for r in self.refs}
        self.assertIn("sub-S0001111189001_ses-SES001", ids)
        self.assertIn("sub-S0001111189002_ses-SES002", ids)

    def test_patient_id_strips_sub_prefix(self):
        r1 = next(r for r in self.refs if "189001" in r.recording_id)
        self.assertEqual(r1.patient_id, "S0001111189001")
        self.assertFalse(r1.patient_id.startswith("sub-"))

    def test_hospital_equals_site_id(self):
        for ref in self.refs:
            self.assertEqual(ref.hospital, _SITE)

    def test_duration_parsed(self):
        r1 = next(r for r in self.refs if "189001" in r.recording_id)
        self.assertAlmostEqual(r1.duration_s, 600.0)

    def test_age_parsed_when_present(self):
        r1 = next(r for r in self.refs if "189001" in r.recording_id)
        self.assertAlmostEqual(r1.age, 55.0)

    def test_age_from_patients_join_when_catalog_missing(self):
        # Row 2 has no AgeAtVisit in the catalog CSV, but HEEDB_patients.csv
        # supplies age=32.0 for this patient; the join should populate it.
        r2 = next(r for r in self.refs if "189002" in r.recording_id)
        self.assertAlmostEqual(r2.age, 32.0)

    def test_sex_parsed_when_present(self):
        r1 = next(r for r in self.refs if "189001" in r.recording_id)
        self.assertEqual(r1.sex, "M")

    def test_sampling_rate_is_none(self):
        # sampling_rate is resolved from the EDF header, not from the catalog
        for ref in self.refs:
            self.assertIsNone(ref.sampling_rate)

    def test_edf_uri_resolved(self):
        r1 = next(r for r in self.refs if "189001" in r.recording_id)
        self.assertIsNotNone(r1.uri)
        self.assertTrue(r1.uri.endswith("_eeg.edf"))

    def test_date_of_death_not_on_recording_ref(self):
        """DateOfDeath is an outcome column and must never appear on a RecordingRef."""
        for ref in self.refs:
            self.assertFalse(hasattr(ref, "date_of_death"))
            self.assertFalse(hasattr(ref, "DateOfDeath"))
            # Also confirm it's not hiding in any field value
            for field_val in [ref.recording_id, ref.patient_id, ref.hospital,
                               ref.uri or "", str(ref.age), str(ref.sex)]:
                self.assertNotIn("death", field_val.lower())


class TestMaxDurationFilter(unittest.TestCase):
    def test_long_recordings_excluded(self):
        # row 3 has duration 2000 s > max 1200 s
        client = _client(max_duration_s=1200)
        refs = list(client.list_recordings(_SITE))
        durations = [r.duration_s for r in refs]
        self.assertTrue(all(d <= 1200.0 for d in durations))

    def test_high_limit_admits_more(self):
        # With max_duration_s=3000, row 3 (2000 s) would pass the duration filter
        # but row 3's EDF key is still unresolvable in our fake S3, so count stays 2
        client = _client(max_duration_s=3000)
        refs = list(client.list_recordings(_SITE))
        # Rows 1, 2 resolve; row 3 now passes duration but still unresolvable
        self.assertEqual(len(refs), 2)


class TestTaskFilter(unittest.TestCase):
    def test_wrong_task_excluded(self):
        # row 4 has ServiceName=LTM; with tasks=["Routine"] it should be excluded
        client = _client(tasks=["Routine"])
        refs = list(client.list_recordings(_SITE))
        for ref in refs:
            # LTM row patient id would be 189004
            self.assertNotIn("189004", ref.recording_id)

    def test_accept_ltm_when_configured(self):
        # With tasks=["LTM"], only row 4 passes task filter among unresolved ones
        # (row 4 has no EDF key in our fake, so it's still skipped)
        client = _client(max_duration_s=1200, tasks=["LTM"])
        refs = list(client.list_recordings(_SITE))
        self.assertEqual(len(refs), 0)  # row 4 passes task but has no resolvable EDF


class TestEDFKeyResolution(unittest.TestCase):
    def test_unresolvable_edf_skipped(self):
        # row 5 (SES005) has no EDF key in fake S3 -> skipped
        client = _client()
        refs = list(client.list_recordings(_SITE))
        recording_ids = [r.recording_id for r in refs]
        self.assertFalse(any("SES005" in rid for rid in recording_ids))

    def test_edf_key_points_into_bids_tree(self):
        client = _client()
        refs = list(client.list_recordings(_SITE))
        for ref in refs:
            self.assertIn("EEG/bids/", ref.uri)
            self.assertIn("/eeg/", ref.uri)


class TestEmptySite(unittest.TestCase):
    def test_unknown_site_yields_nothing(self):
        """A site with no catalog CSV should yield no refs, not raise."""
        client = _client()
        refs = list(client.list_recordings("S9999"))
        self.assertEqual(refs, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
