"""TUH rsync transport -- command construction + manifest, no ssh/network.

Injects a fake runner so the exact NEDC rsync command, the TEST connectivity
probe, and the manifest->RecordingRef mapping are testable with the standard
library alone.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.tuh_fetch import TUHRsyncClient


class _FakeRunner:
    def __init__(self, rc=0, out="sent 1 file", err=""):
        self.rc, self.out, self.err = rc, out, err
        self.cmds: list[list[str]] = []

    def __call__(self, cmd):
        self.cmds.append(cmd)
        return self.rc, self.out, self.err


def _cfg(manifest=""):
    return {
        "external_replication": {
            "enabled": True,
            "tuh": {
                "host": "www.isip.piconepress.com",
                "user": "nedc-tuh-eeg",
                "ssh_key": "~/.ssh/id_ed25519",
                "remote_root": "data/tuh_eeg",
                "test_path": "data/tuh_eeg/TEST",
                "scratch_dir": tempfile.mkdtemp(),
                "manifest": manifest,
                "manifest_format": "tsv",
                "manifest_columns": {
                    "recording_id": "recording_id", "patient_id": "patient_id",
                    "object_key": "edf_path", "sampling_rate": "sfreq",
                    "age": "age", "sex": "sex"},
            },
        },
    }


class TestRsyncCommand(unittest.TestCase):
    def test_matches_nedc_documented_command(self):
        c = TUHRsyncClient(_cfg(), runner=_FakeRunner())
        cmd = c.rsync_cmd("data/tuh_eeg/TEST", "/tmp/dest")
        self.assertEqual(cmd[0], "rsync")
        self.assertIn("-auvxL", cmd)
        # -e "ssh -i <key> ..."
        e_idx = cmd.index("-e")
        self.assertTrue(cmd[e_idx + 1].startswith("ssh -i "))
        self.assertIn("id_ed25519", cmd[e_idx + 1])
        # user@host:remote then dest, in order, last two args
        self.assertEqual(cmd[-2], "nedc-tuh-eeg@www.isip.piconepress.com:data/tuh_eeg/TEST")
        self.assertEqual(cmd[-1], "/tmp/dest")

    def test_test_connection_ok(self):
        runner = _FakeRunner(rc=0)
        res = TUHRsyncClient(_cfg(), runner=runner).test_connection()
        self.assertTrue(res["ok"])
        self.assertIn("data/tuh_eeg/TEST", res["cmd"])
        self.assertEqual(len(runner.cmds), 1)

    def test_test_connection_failure_reports(self):
        runner = _FakeRunner(rc=255, err="Permission denied (publickey).")
        res = TUHRsyncClient(_cfg(), runner=runner).test_connection()
        self.assertFalse(res["ok"])
        self.assertEqual(res["returncode"], 255)
        self.assertIn("publickey", res["stderr"])


class TestManifest(unittest.TestCase):
    def test_list_recordings_from_manifest(self):
        p = os.path.join(tempfile.mkdtemp(), "tuh.tsv")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("recording_id\tpatient_id\tedf_path\tsfreq\tage\tsex\n")
            fh.write("t1\tq1\tdata/tuh_eeg/edf/aaaaaaaa.edf\t250\t55\tM\n")
            fh.write("t2\tq2\tdata/tuh_eeg/edf/bbbbbbbb.edf\t256\t72\tF\n")
        refs = list(TUHRsyncClient(_cfg(manifest=p), runner=_FakeRunner()).list_recordings())
        self.assertEqual([r.recording_id for r in refs], ["t1", "t2"])
        self.assertTrue(all(r.hospital == "TUH" for r in refs))
        self.assertEqual(refs[0].uri, "data/tuh_eeg/edf/aaaaaaaa.edf")
        self.assertEqual(refs[1].age, 72.0)

    def test_missing_manifest_raises(self):
        with self.assertRaises(FileNotFoundError):
            list(TUHRsyncClient(_cfg(manifest=""), runner=_FakeRunner()).list_recordings())


if __name__ == "__main__":
    unittest.main(verbosity=2)
