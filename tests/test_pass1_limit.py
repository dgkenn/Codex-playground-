"""Pass-1 pilot cap (`--limit` / execution.max_recordings) -- stdlib only.

Patches process_recording so the streaming/limit logic is testable without mne,
torch, or a real transport.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import run_pass1
from pipeline.stream_fetch import RecordingRef, _BDSPClient


class _FakeClient(_BDSPClient):
    def __init__(self, cfg, n_per_site=10):
        super().__init__(cfg)
        self.n = n_per_site

    def list_recordings(self, hospital):
        for i in range(self.n):
            yield RecordingRef(recording_id=f"{hospital}-{i}",
                               patient_id=f"{hospital}-p{i}", hospital=hospital,
                               age=50.0)


class _FakeWriter:
    def __init__(self):
        self.rows = []

    def write_row(self, row):
        self.rows.append(row)

    def flush(self):
        pass


def _cfg():
    d = tempfile.mkdtemp()
    return {
        "phase": 1,
        "seed": 0,
        "cohort": {"primary_min_age_years": 18},
        "sites": {"discovery": ["MGH", "BWH"], "held_out": "BIDMC"},
        "execution": {"shard_size_recordings": 4, "max_recordings": None},
        "artifacts_dir": d, "log_dir": os.path.join(d, "logs"),
    }


def _row(cfg, ref, embedder, client):
    return {"recording_id": ref.recording_id, "embedding": [0.0],
            "features": {}, "n_windows": 1}


class TestPilotCap(unittest.TestCase):
    def test_limit_caps_consumption(self):
        cfg = _cfg()
        w = _FakeWriter()
        with mock.patch.object(run_pass1, "process_recording", _row):
            s = run_pass1.run(cfg, w, embedder=object(),
                              client=_FakeClient(cfg), limit=3)
        self.assertEqual(s["n_consumed"], 3)
        self.assertEqual(s["n_written"], 3)
        self.assertTrue(s["hit_limit"])
        self.assertEqual(len(w.rows), 3)

    def test_config_max_recordings_used_when_no_arg(self):
        cfg = _cfg()
        cfg["execution"]["max_recordings"] = 5
        w = _FakeWriter()
        with mock.patch.object(run_pass1, "process_recording", _row):
            s = run_pass1.run(cfg, w, embedder=object(), client=_FakeClient(cfg))
        self.assertEqual(s["n_consumed"], 5)
        self.assertTrue(s["hit_limit"])

    def test_no_cap_processes_all_eligible(self):
        cfg = _cfg()
        w = _FakeWriter()
        with mock.patch.object(run_pass1, "process_recording", _row):
            s = run_pass1.run(cfg, w, embedder=object(),
                              client=_FakeClient(cfg, n_per_site=6), limit=0)
        self.assertEqual(s["n_written"], 12)   # 6 x 2 discovery sites
        self.assertFalse(s["hit_limit"])

    def test_resume_does_not_count_completed_toward_limit(self):
        cfg = _cfg()
        run_pass1.mark_completed(cfg, "MGH-0")   # pretend already done
        run_pass1.mark_completed(cfg, "MGH-1")
        w = _FakeWriter()
        with mock.patch.object(run_pass1, "process_recording", _row):
            s = run_pass1.run(cfg, w, embedder=object(),
                              client=_FakeClient(cfg), limit=3)
        # 3 NEW recordings consumed; the 2 pre-completed are skipped first.
        self.assertEqual(s["n_consumed"], 3)
        self.assertNotIn("MGH-0", [r["recording_id"] for r in w.rows])


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestWindowCap(unittest.TestCase):
    def test_select_window_indices(self):
        from pipeline.embed import select_window_indices
        self.assertEqual(select_window_indices(10, None), list(range(10)))
        self.assertEqual(select_window_indices(5, 40), [0, 1, 2, 3, 4])  # n<=cap -> all
        idx = select_window_indices(1000, 40)
        self.assertEqual(len(idx), 40)
        self.assertEqual(idx, sorted(idx))                 # increasing
        self.assertTrue(0 == idx[0] and idx[-1] <= 999)    # spans the recording
        self.assertEqual(len(set(idx)), 40)                # distinct
        self.assertEqual(idx, select_window_indices(1000, 40))  # deterministic
