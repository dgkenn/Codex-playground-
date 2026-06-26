"""test_inspire_autofetch.py -- offline unit tests for vitaldb_aki/inspire/auto_fetch.py

All tests are offline: no network access, no credentials required.
Tests use monkeypatch/subprocess mocking to simulate access checks and downloads.

Run:
    python3 -m unittest vitaldb_aki.tests.test_inspire_autofetch -v

Coverage:
  1. auto_fetch with existing DOWNLOAD_COMPLETE sentinel -> skip (idempotent)
  2. auto_fetch with HTTP 403 access denied -> return status "gated", no files created
  3. auto_fetch with HTTP 200 access granted, fake zip on temp dir -> downloads/extracts/sentinel
  4. auto_fetch import and call does not crash
  5. run_all.py still imports after wiring in auto_fetch step
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

# Ensure package root on sys.path when run directly
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


class TestAutoFetch(unittest.TestCase):
    """Offline tests for auto_fetch."""

    def setUp(self):
        """Create a temp directory for each test."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temp directory."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_already_downloaded_idempotent(self):
        """If DOWNLOAD_COMPLETE sentinel exists, auto_fetch skips and returns immediately."""
        from vitaldb_aki.inspire.auto_fetch import auto_fetch

        # Create sentinel
        sentinel_path = os.path.join(self.temp_dir, "DOWNLOAD_COMPLETE")
        with open(sentinel_path, "w") as fh:
            fh.write("already downloaded")

        result = auto_fetch(dest=self.temp_dir)
        self.assertEqual(result["status"], "already_downloaded")

    def test_access_denied_gated(self):
        """If HTTP 403 (access denied), auto_fetch returns gated and creates no files."""
        from vitaldb_aki.inspire.auto_fetch import auto_fetch

        # Mock _test_access to return HTTP 403
        with mock.patch("vitaldb_aki.inspire.auto_fetch._test_access") as mock_test:
            mock_test.return_value = (False, 403)

            result = auto_fetch(dest=self.temp_dir)

            self.assertEqual(result["status"], "gated")
            self.assertEqual(result["http"], 403)

            # Verify no files created (except cache dir itself)
            self.assertFalse(os.path.exists(os.path.join(self.temp_dir, "DOWNLOAD_COMPLETE")))

    def test_access_granted_downloads_and_unzips(self):
        """If HTTP 200, auto_fetch downloads a fake zip, unzips, and writes sentinel."""
        from vitaldb_aki.inspire.auto_fetch import auto_fetch

        # Create a fake zip file in a temp location
        fake_zip_dir = tempfile.mkdtemp()
        try:
            fake_zip_path = os.path.join(fake_zip_dir, "inspire_1.4.2.zip")
            with zipfile.ZipFile(fake_zip_path, "w") as zf:
                zf.writestr("inspire/data.txt", "fake INSPIRE data")

            # Mock _test_access to return HTTP 200 (approved)
            # Mock subprocess.run to simulate successful wget (copy fake zip instead)
            def mock_wget(*args, **kwargs):
                # args[0] is the command list, which contains the output path
                cmd = args[0] if args else kwargs.get("args", [])
                output_idx = cmd.index("-O") + 1 if "-O" in cmd else None
                if output_idx:
                    dest_zip = cmd[output_idx]
                    shutil.copy(fake_zip_path, dest_zip)
                # Return success
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

            with mock.patch("vitaldb_aki.inspire.auto_fetch._test_access") as mock_test, \
                 mock.patch("subprocess.run") as mock_run:
                mock_test.return_value = (True, 200)
                mock_run.side_effect = mock_wget

                result = auto_fetch(dest=self.temp_dir)

                self.assertEqual(result["status"], "downloaded")
                self.assertEqual(result["path"], self.temp_dir)

                # Verify sentinel was created
                sentinel_path = os.path.join(self.temp_dir, "DOWNLOAD_COMPLETE")
                self.assertTrue(os.path.exists(sentinel_path))

                # Verify zip was extracted
                extracted_data_path = os.path.join(self.temp_dir, "inspire", "data.txt")
                self.assertTrue(os.path.exists(extracted_data_path))
                with open(extracted_data_path) as fh:
                    self.assertEqual(fh.read(), "fake INSPIRE data")
        finally:
            if os.path.exists(fake_zip_dir):
                shutil.rmtree(fake_zip_dir)

    def test_network_error_returns_error_status(self):
        """If _test_access raises an exception, auto_fetch returns error status."""
        from vitaldb_aki.inspire.auto_fetch import auto_fetch

        # Mock _test_access to raise an exception
        with mock.patch("vitaldb_aki.inspire.auto_fetch._test_access") as mock_test:
            mock_test.side_effect = Exception("network error")

            result = auto_fetch(dest=self.temp_dir)

            self.assertEqual(result["status"], "error")
            self.assertIn("access test failed", result["msg"])

    def test_download_failure_returns_error_status(self):
        """If wget fails, auto_fetch returns error status and does not create sentinel."""
        from vitaldb_aki.inspire.auto_fetch import auto_fetch

        # Mock _test_access to return success but wget to fail
        with mock.patch("vitaldb_aki.inspire.auto_fetch._test_access") as mock_test, \
             mock.patch("subprocess.run") as mock_run:
            mock_test.return_value = (True, 200)
            # Simulate wget failure
            mock_run.return_value = subprocess.CompletedProcess(
                args=["wget"], returncode=1, stdout="", stderr="wget error"
            )

            result = auto_fetch(dest=self.temp_dir)

            self.assertEqual(result["status"], "error")
            self.assertIn("wget failed", result["msg"])

            # Verify sentinel was not created
            sentinel_path = os.path.join(self.temp_dir, "DOWNLOAD_COMPLETE")
            self.assertFalse(os.path.exists(sentinel_path))

    def test_auto_fetch_importable(self):
        """auto_fetch module imports without error."""
        from vitaldb_aki.inspire import auto_fetch
        self.assertTrue(hasattr(auto_fetch, "auto_fetch"))

    def test_run_all_imports_after_wiring(self):
        """run_all.py still imports successfully (no syntax errors from wiring)."""
        # This is a basic smoke test; the actual integration test is in run_all.py
        import vitaldb_aki.run_all
        self.assertTrue(hasattr(vitaldb_aki.run_all, "main"))


class TestAutoFetchIntegration(unittest.TestCase):
    """Integration test: verify auto_fetch call signature matches run_all expectations."""

    def test_auto_fetch_returns_dict_with_status(self):
        """auto_fetch always returns a dict with 'status' key."""
        from vitaldb_aki.inspire.auto_fetch import auto_fetch

        temp_dir = tempfile.mkdtemp()
        try:
            # Mock to simulate gated access
            with mock.patch("vitaldb_aki.inspire.auto_fetch._test_access") as mock_test:
                mock_test.return_value = (False, 403)
                result = auto_fetch(dest=temp_dir)
                self.assertIsInstance(result, dict)
                self.assertIn("status", result)
        finally:
            shutil.rmtree(temp_dir)

    def test_auto_fetch_never_raises(self):
        """auto_fetch catches all exceptions and returns error status (never raises)."""
        from vitaldb_aki.inspire.auto_fetch import auto_fetch

        temp_dir = tempfile.mkdtemp()
        try:
            # Mock to simulate any exception
            with mock.patch("vitaldb_aki.inspire.auto_fetch._test_access") as mock_test:
                mock_test.side_effect = RuntimeError("simulated crash")
                # Should not raise; should return error status
                result = auto_fetch(dest=temp_dir)
                self.assertEqual(result["status"], "error")
                self.assertIsInstance(result, dict)
        finally:
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    unittest.main()
