"""BDSP S3 client -- catalog parsing + firewall filtering, no AWS required.

A fake S3 object (just `get_object`) is injected, so the catalog->RecordingRef
mapping and the held-out/eligibility filtering are testable with the standard
library alone. The actual EDF download + mne read are an integration concern
(need real credentials + signal) and are not exercised here.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from guards.heldout_guard import FirewallBreach, HeldoutGuard
from pipeline.stream_fetch import BDSPS3Client, iter_qualifying_recordings, make_client


_CATALOG_TSV = (
    "recording_id\tpatient_id\tsite\tedf_path\tsfreq\tage\tsex\tcare_setting\tdevice\tduration_s\n"
    "r1\tp1\tMGH\tHEEDB/sub-p1/eeg/r1.edf\t256\t64\tM\tICU\tnk\t1200\n"
    "r2\tp2\tBWH\tHEEDB/sub-p2/eeg/r2.edf\t200\t45\tF\tEMU\txltek\t900\n"
    "r3\tp3\tMGH\tHEEDB/sub-p3/eeg/r3.edf\t512\t15\tM\troutine\tnk\t600\n"   # pediatric -> excluded
    "r4\tp1\tMGH\tHEEDB/sub-p1/eeg/r4.edf\t256\t64\tM\tICU\tnk\t1000\n"      # dup patient -> excluded
    "r5\tp5\tBIDMC\tHEEDB/sub-p5/eeg/r5.edf\t256\t70\tF\tICU\tnk\t1500\n"    # held-out site
)


class _FakeBody:
    def __init__(self, data: bytes):
        self._b = io.BytesIO(data)

    def read(self):
        return self._b.read()


class _FakeS3:
    def __init__(self, blob: bytes):
        self.blob = blob
        self.calls = []

    def get_object(self, Bucket, Key):  # noqa: N803 (boto3 kwarg names)
        self.calls.append((Bucket, Key))
        return {"Body": _FakeBody(self.blob)}


def _cfg():
    return {
        "phase": 1,
        "cohort": {"primary_min_age_years": 18},
        "sites": {"discovery": ["MGH", "BWH"], "held_out": "BIDMC"},
        "log_dir": "/tmp/bdsp_test_logs",
        "data": {
            "source": "BDSP",
            "scratch_dir": "/tmp/heedb_scratch",
            "s3": {
                "access_point": "arn:aws:s3:us-east-1:0:accesspoint/test-ap",
                "region": "us-east-1",
                "catalog_key": "HEEDB/index.tsv",
                "catalog_format": "tsv",
                "catalog_columns": {
                    "recording_id": "recording_id", "patient_id": "patient_id",
                    "hospital": "site", "object_key": "edf_path",
                    "sampling_rate": "sfreq", "age": "age", "sex": "sex",
                    "care_setting": "care_setting", "device": "device",
                    "duration_s": "duration_s"},
            },
        },
    }


class TestFactory(unittest.TestCase):
    def test_make_client_returns_s3_client(self):
        self.assertIsInstance(make_client(_cfg()), BDSPS3Client)


class TestCatalogMapping(unittest.TestCase):
    def setUp(self):
        self.client = BDSPS3Client(_cfg(), s3=_FakeS3(_CATALOG_TSV.encode()))

    def test_maps_acquisition_metadata(self):
        refs = list(self.client.list_recordings("MGH"))
        self.assertEqual({r.recording_id for r in refs}, {"r1", "r3", "r4"})
        r1 = next(r for r in refs if r.recording_id == "r1")
        self.assertEqual(r1.hospital, "MGH")
        self.assertEqual(r1.patient_id, "p1")
        self.assertEqual(r1.sampling_rate, 256.0)
        self.assertEqual(r1.age, 64.0)
        self.assertEqual(r1.care_setting, "ICU")
        self.assertEqual(r1.uri, "HEEDB/sub-p1/eeg/r1.edf")

    def test_filters_by_hospital(self):
        self.assertEqual([r.recording_id for r in self.client.list_recordings("BWH")],
                         ["r2"])

    def test_catalog_cached_single_get(self):
        list(self.client.list_recordings("MGH"))
        list(self.client.list_recordings("BWH"))
        self.assertEqual(len(self.client._s3.calls), 1)  # catalog read once


class TestFirewallAndEligibility(unittest.TestCase):
    def test_heldout_excluded_age_and_dup_filtered(self):
        cfg = _cfg()
        client = BDSPS3Client(cfg, s3=_FakeS3(_CATALOG_TSV.encode()))
        guard = HeldoutGuard(cfg)
        got = [r.recording_id for r in iter_qualifying_recordings(cfg, guard, client)]
        # r1 (MGH, 64, p1), r2 (BWH, 45, p2). r3 pediatric, r4 dup patient,
        # r5 held-out (never even listed for discovery sites).
        self.assertEqual(sorted(got), ["r1", "r2"])

    def test_heldout_site_access_is_blocked(self):
        cfg = _cfg()
        guard = HeldoutGuard(cfg)
        with self.assertRaises(FirewallBreach):
            guard.check_site_access("BIDMC", context="test")


if __name__ == "__main__":
    unittest.main(verbosity=2)
