"""test_cross_waveform_streaming.py -- Tests for disk-bounded streaming mechanism.

Verifies:
  1. purge_track() deletes the right cached file and is a no-op when absent.
  2. download_track() without purge still caches (backward-compatible).
  3. cross_waveform.extract() calls purge for each of the three big SNUADC
     tracks after feature extraction (monkeypatched download + purge).

All tests are offline / synthetic: no network access, no VitalDB credentials.

Run:
    python3 -m pytest vitaldb_aki/tests/test_cross_waveform_streaming.py -v
    # or
    python3 -m unittest vitaldb_aki.tests.test_cross_waveform_streaming -v
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from vitaldb_aki.data import tracks as tracks_mod
from vitaldb_aki.features import cross_waveform as cw_mod


# ---------------------------------------------------------------------------
# Minimal synthetic config (no real API needed).
# ---------------------------------------------------------------------------

def _make_cfg(cache_dir: str) -> dict:
    return {
        "data": {
            "cache_dir": cache_dir,
            "api_base": "http://fake.invalid/api",
        }
    }


def _write_fake_csv(path: str, content: str = "Time,Value\n0.0,1.0\n1.0,2.0\n") -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


# ---------------------------------------------------------------------------
# 1. purge_track tests
# ---------------------------------------------------------------------------

class TestPurgeTrack(unittest.TestCase):

    def _setup(self, tmp: str, caseid: str = "42", tname: str = "SNUADC/ECG_II",
               tid: str = "tid_ecg"):
        """Wire up a fake tid_for and create the corresponding cached CSV."""
        cfg = _make_cfg(tmp)
        tdir = os.path.join(tmp, "tracks")
        path = os.path.join(tdir, f"{tid}.csv")
        _write_fake_csv(path)
        return cfg, path

    def test_purge_deletes_existing_file(self):
        """purge_track removes the cached CSV when it exists."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg, path = self._setup(tmp)
            self.assertTrue(os.path.exists(path))

            with patch.object(tracks_mod, "tid_for", return_value="tid_ecg"):
                tracks_mod.purge_track(cfg, "42", "SNUADC/ECG_II")

            self.assertFalse(os.path.exists(path),
                             "purge_track should have deleted the cached CSV")

    def test_purge_noop_when_file_absent(self):
        """purge_track does not raise when the cached file does not exist."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _make_cfg(tmp)
            # The tracks/ dir exists but the file does not.
            os.makedirs(os.path.join(tmp, "tracks"), exist_ok=True)

            with patch.object(tracks_mod, "tid_for", return_value="tid_ecg"):
                # Must not raise
                tracks_mod.purge_track(cfg, "42", "SNUADC/ECG_II")

    def test_purge_noop_when_tid_not_in_index(self):
        """purge_track is a no-op when tid_for returns None (track not in index)."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _make_cfg(tmp)
            with patch.object(tracks_mod, "tid_for", return_value=None):
                # Must not raise, must not touch any file
                tracks_mod.purge_track(cfg, "42", "SNUADC/ECG_II")

    def test_purge_nonfatal_on_oserror(self):
        """purge_track logs a warning and returns normally when os.remove raises OSError."""
        import logging
        with tempfile.TemporaryDirectory() as tmp:
            cfg, path = self._setup(tmp)

            def _raise_perm(p):
                raise OSError("permission denied")

            with patch.object(tracks_mod, "tid_for", return_value="tid_ecg"), \
                 patch("os.remove", side_effect=_raise_perm), \
                 self.assertLogs(tracks_mod._log.name, level="WARNING"):
                tracks_mod.purge_track(cfg, "42", "SNUADC/ECG_II")
            # No exception propagated

    def test_purge_only_targets_correct_file(self):
        """purge_track deletes only the file for the given (caseid, tname) pair."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _make_cfg(tmp)
            tdir = os.path.join(tmp, "tracks")

            # Two cached files: ECG (tid=100) and PLETH (tid=200)
            ecg_path = os.path.join(tdir, "100.csv")
            pleth_path = os.path.join(tdir, "200.csv")
            _write_fake_csv(ecg_path)
            _write_fake_csv(pleth_path)

            def _fake_tid(cfg2, caseid, tname):
                return "100" if tname == "SNUADC/ECG_II" else "200"

            with patch.object(tracks_mod, "tid_for", side_effect=_fake_tid):
                tracks_mod.purge_track(cfg, "42", "SNUADC/ECG_II")

            # ECG file gone, PLETH file intact
            self.assertFalse(os.path.exists(ecg_path))
            self.assertTrue(os.path.exists(pleth_path))


# ---------------------------------------------------------------------------
# 2. Backward-compatibility: download_track still caches without purging
# ---------------------------------------------------------------------------

class TestDownloadTrackBackwardCompat(unittest.TestCase):

    def test_download_track_leaves_file_cached(self):
        """download_track with no purge leaves the CSV on disk (existing callers)."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _make_cfg(tmp)
            tdir = os.path.join(tmp, "tracks")
            path = os.path.join(tdir, "tid_art.csv")
            _write_fake_csv(path, "Time,Value\n0.0,75.0\n1.0,76.0\n")

            with patch.object(tracks_mod, "tid_for", return_value="tid_art"):
                result = tracks_mod.download_track(cfg, "42", "SNUADC/ART")

            # File still exists (not purged)
            self.assertTrue(os.path.exists(path),
                            "download_track must not delete the cached file")
            self.assertEqual(len(result), 2,
                             "should have parsed 2 numeric rows")

    def test_download_track_signature_unchanged(self):
        """download_track still accepts (cfg, caseid, tname, refresh=False)."""
        import inspect
        sig = inspect.signature(tracks_mod.download_track)
        params = list(sig.parameters.keys())
        self.assertIn("cfg", params)
        self.assertIn("caseid", params)
        self.assertIn("tname", params)
        self.assertIn("refresh", params)

    def test_purge_track_is_exported(self):
        """purge_track is importable from the tracks module."""
        self.assertTrue(hasattr(tracks_mod, "purge_track"),
                        "tracks module must export purge_track")
        self.assertTrue(callable(tracks_mod.purge_track))

    def test_streamed_track_is_exported(self):
        """streamed_track context manager is importable from the tracks module."""
        self.assertTrue(hasattr(tracks_mod, "streamed_track"),
                        "tracks module must export streamed_track")


# ---------------------------------------------------------------------------
# 3. cross_waveform.extract() calls purge for each big SNUADC track per case
# ---------------------------------------------------------------------------

class TestExtractCallsPurge(unittest.TestCase):
    """Monkeypatches load_snuadc_waveform and purge_track to verify the
    streaming contract without touching the network or the disk."""

    def _make_case(self, caseid="42"):
        return {caseid: {"caseid": caseid, "opstart": 0.0, "opend": 7200.0,
                         "anestart": 0.0}}

    def test_purge_called_for_all_three_snuadc_tracks(self):
        """extract() must call purge_track for ECG, PLETH, ART for each case."""
        purged: list[tuple[str, str]] = []

        def _fake_purge(cfg, caseid, tname):
            purged.append((str(caseid), tname))

        # load_snuadc_waveform returns (None, None) -> all features None, but
        # purge must still be called (try/finally guarantees this).
        with patch.object(cw_mod, "load_snuadc_waveform", return_value=(None, None)), \
             patch("vitaldb_aki.data.tracks.purge_track", side_effect=_fake_purge):
            cfg = _make_cfg("/nonexistent/cache")
            cases_by_id = self._make_case("42")
            cw_mod.extract(cfg, cases_by_id, ["42"])

        purged_tnames = [t for (_, t) in purged]
        self.assertIn(cw_mod.ECG_TRACK, purged_tnames,
                      "ECG_TRACK must be purged")
        self.assertIn(cw_mod.PPG_TRACK, purged_tnames,
                      "PPG_TRACK (PLETH) must be purged")
        self.assertIn(cw_mod.ART_TRACK, purged_tnames,
                      "ART_TRACK must be purged")

    def test_purge_called_even_on_exception(self):
        """Purge runs even when feature extraction raises (try/finally)."""
        purged: list[str] = []

        def _fake_purge(cfg, caseid, tname):
            purged.append(tname)

        def _raise(*a, **kw):
            raise RuntimeError("synthetic extraction failure")

        with patch.object(cw_mod, "load_snuadc_waveform", side_effect=_raise), \
             patch("vitaldb_aki.data.tracks.purge_track", side_effect=_fake_purge):
            cfg = _make_cfg("/nonexistent/cache")
            cases_by_id = self._make_case("99")
            # Exception inside try block -> finally must still fire
            try:
                cw_mod.extract(cfg, cases_by_id, ["99"])
            except Exception:
                pass

        # At least one purge call must have been made
        self.assertGreater(len(purged), 0,
                           "purge_track must be called even when extraction raises")

    def test_purge_not_called_for_co2_track(self):
        """Primus/CO2 must NOT be purged (it's small; leave it cached)."""
        purged: list[str] = []

        def _fake_purge(cfg, caseid, tname):
            purged.append(tname)

        with patch.object(cw_mod, "load_snuadc_waveform", return_value=(None, None)), \
             patch("vitaldb_aki.data.tracks.purge_track", side_effect=_fake_purge):
            cfg = _make_cfg("/nonexistent/cache")
            cases_by_id = self._make_case("5")
            cw_mod.extract(cfg, cases_by_id, ["5"])

        self.assertNotIn(cw_mod.CO2_TRACK, purged,
                         "Primus/CO2 must NOT be purged")

    def test_purge_called_for_each_case_independently(self):
        """Purge is scoped per case: each case gets its own purge calls."""
        purged_by_case: dict[str, list[str]] = {}

        def _fake_purge(cfg, caseid, tname):
            purged_by_case.setdefault(str(caseid), []).append(tname)

        cases_by_id = {
            "1": {"caseid": "1", "opstart": 0.0, "opend": 7200.0, "anestart": 0.0},
            "2": {"caseid": "2", "opstart": 0.0, "opend": 7200.0, "anestart": 0.0},
        }
        with patch.object(cw_mod, "load_snuadc_waveform", return_value=(None, None)), \
             patch("vitaldb_aki.data.tracks.purge_track", side_effect=_fake_purge):
            cfg = _make_cfg("/nonexistent/cache")
            cw_mod.extract(cfg, cases_by_id, ["1", "2"])

        for cid in ("1", "2"):
            self.assertIn(cid, purged_by_case,
                          f"case {cid} should have purge calls")
            self.assertIn(cw_mod.ECG_TRACK, purged_by_case[cid])
            self.assertIn(cw_mod.PPG_TRACK, purged_by_case[cid])
            self.assertIn(cw_mod.ART_TRACK, purged_by_case[cid])

    def test_result_returned_normally_after_purge(self):
        """extract() returns a valid dict even when purge is called."""
        with patch.object(cw_mod, "load_snuadc_waveform", return_value=(None, None)), \
             patch("vitaldb_aki.data.tracks.purge_track"):
            cfg = _make_cfg("/nonexistent/cache")
            cases_by_id = self._make_case("7")
            result = cw_mod.extract(cfg, cases_by_id, ["7"])

        self.assertIn("7", result)
        row = result["7"]
        self.assertIn("cross_waveform_available", row)
        self.assertEqual(row["cross_waveform_available"], 0)
        # All feature values should be None (no channels available)
        for spec in cw_mod.SPECS:
            if spec.name == "cross_waveform_available":
                continue
            self.assertIsNone(row.get(spec.name),
                              f"{spec.name} should be None when no channels available")

    def test_missing_caseid_still_gets_none_row(self):
        """A caseid absent from cases_by_id returns a none_row without purge attempts."""
        purged: list[str] = []

        def _fake_purge(cfg, caseid, tname):
            purged.append(tname)

        with patch("vitaldb_aki.data.tracks.purge_track", side_effect=_fake_purge):
            cfg = _make_cfg("/nonexistent/cache")
            result = cw_mod.extract(cfg, {}, ["999"])

        # caseid not in cases_by_id -> early continue before try/finally
        self.assertIn("999", result)
        self.assertEqual(result["999"]["cross_waveform_available"], 0)
        # No purge should have been called for the missing case
        self.assertEqual(purged, [],
                         "purge must not be called for cases absent from cases_by_id")


# ---------------------------------------------------------------------------
# 4. streamed_track context manager
# ---------------------------------------------------------------------------

class TestStreamedTrack(unittest.TestCase):

    def test_streamed_track_yields_series_and_purges(self):
        """streamed_track yields the parsed series and deletes the file on exit."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _make_cfg(tmp)
            tdir = os.path.join(tmp, "tracks")
            path = os.path.join(tdir, "tid_ecg.csv")
            _write_fake_csv(path, "Time,Value\n0.0,1.0\n1.0,2.0\n")

            with patch.object(tracks_mod, "tid_for", return_value="tid_ecg"):
                with tracks_mod.streamed_track(cfg, "42", "SNUADC/ECG_II") as series:
                    self.assertEqual(len(series), 2)
                    # File still present while inside the context
                    self.assertTrue(os.path.exists(path))

            # File gone after context exit
            self.assertFalse(os.path.exists(path),
                             "streamed_track must delete the file on exit")

    def test_streamed_track_purges_on_exception(self):
        """streamed_track deletes the file even when an exception is raised inside."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _make_cfg(tmp)
            tdir = os.path.join(tmp, "tracks")
            path = os.path.join(tdir, "tid_ecg.csv")
            _write_fake_csv(path)

            with patch.object(tracks_mod, "tid_for", return_value="tid_ecg"):
                try:
                    with tracks_mod.streamed_track(cfg, "42", "SNUADC/ECG_II") as series:
                        raise ValueError("deliberate error inside context")
                except ValueError:
                    pass

            self.assertFalse(os.path.exists(path),
                             "file must be deleted even when exception raised inside context")

    def test_streamed_track_yields_empty_when_absent(self):
        """streamed_track yields [] when the track is absent from the index."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _make_cfg(tmp)
            with patch.object(tracks_mod, "tid_for", return_value=None):
                with tracks_mod.streamed_track(cfg, "42", "SNUADC/ECG_II") as series:
                    self.assertEqual(series, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
