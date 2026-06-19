"""test_local_edf_integration.py -- REAL signal path end-to-end on real EDF bytes.

Proves the complete Phase-1 signal path using:
  local .edf file (written via mne export / edfio backend)
  -> mne harmonization (pick/reference/notch/bandpass/resample/window/artifact-reject)
  -> deterministic stub embedder (fixed random projection in lieu of CBraMod/torch)
  -> interpretable features (REAL band-power + aperiodic DSP on the synthesized signal)
  -> compact tables
  -> Phase-1 analysis (run_phase1)

Design decisions
----------------
* Real .edf round-trip: each synthesized recording is written to a temp dir as an
  actual .edf file (mne.RawArray.export(..., fmt='edf')) and then read back via
  mne.io.read_raw_edf, exercising real file I/O and the EDF parser.
* StubEmbedder: replaces FrozenEmbedder (CBraMod/torch, not available here) with a
  deterministic random-projection that satisfies run_pass1's embed_windows(windows)
  contract -- returns (n_windows, d) float32. Seeded for reproducibility.
* Small signals: ~45 s at 200 Hz (model sfreq), 4 channels (base_cfg's list),
  so the test runs in a few seconds.
* Known oscillation: alpha-band (10 Hz) sine injected on top of pink-ish noise so
  that band-power and aperiodic features are non-trivial / non-NaN.

Skipped automatically when mne or scikit-learn is not importable.
"""
from __future__ import annotations

import math
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import mne          # noqa: F401
    import sklearn      # noqa: F401
    import numpy as np
    HAVE_STACK = True
except ImportError:
    HAVE_STACK = False

from tests.test_integrity import base_cfg


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cfg(artifacts_dir: str, log_dir: str, edf_dir: str,
              recordings: list[dict]) -> dict:
    """Build a full Phase-1 config wired to the local EDF source."""
    cfg = base_cfg(phase=1)
    cfg["artifacts_dir"] = artifacts_dir
    cfg["log_dir"] = log_dir

    # Discovery hospitals must match the manifest entries.
    cfg["sites"] = {
        "discovery": ["MGH", "BWH"],
        "held_out": "BIDMC",
        "reproducibility_ari_threshold": 0.5,
    }

    # LocalEDFClient config.
    cfg["data"] = {
        "source": "local_edf",
        "access_mode": "stream",
        "local_edf": {
            "dir": edf_dir,
            "recordings": recordings,
        },
    }

    # Model: use the 4-channel set from base_cfg; 45 s window at 200 Hz.
    # We synthesize 45 s of data to guarantee at least one 30-s window.
    cfg["model"]["window_seconds"] = 30
    cfg["model"]["window_stride_seconds"] = 30
    cfg["model"]["expected_sfreq_hz"] = 200

    # Feature config: small set so compute_features runs fast.
    cfg["features"] = {
        "bands": {"delta": [0.5, 4], "theta": [4, 8], "alpha": [8, 13],
                  "beta": [13, 30]},
        "specparam": {"freq_range": [1, 45]},
        "spectral_edge_pct": 95,
        "connectivity": "wpli",
        "entropy": [],          # skip sample_entropy for speed
        "microstates": {"n_states": 4},
    }

    # Phase-1 analysis config.
    cfg["clustering"] = {
        "algorithm": "gmm",
        "k_candidates": [2, 3],
        "k_selection": "consensus_pac",
        "stability_min": 0.0,   # don't gate on stability with tiny N
        "consensus": {
            "n_resamples": 5,
            "subsample_fraction": 0.8,
            "pac_low": 0.1,
            "pac_high": 0.9,
        },
    }
    cfg["site_invariance"] = {
        "route_a_method": "combat",
        "site_probe": {
            "targets": ["hospital"],
            "classifier": "logreg",
            "chance_tolerance_auc": 0.65,
            "cv_folds": 2,
        },
    }
    cfg["audits"] = {
        "acquisition_covariates": ["sampling_rate"],
        "site_purity_reject": 0.95,
        "negative_controls": {"surrogate_n": 5},   # fast: 5 surrogates
    }
    cfg["execution"]["shard_size_recordings"] = 10
    return cfg


def _write_edf(path: str, ch_names: list[str], sfreq: float,
               duration_s: float, seed: int, alpha_amp: float = 3e-5) -> None:
    """Synthesize multi-channel EEG and save as a real .edf file.

    Signal model:
      - Pink-ish noise (1/f approximation: white noise low-pass filtered at 60 Hz)
        scaled to ~10 µV RMS, simulating background EEG.
      - An alpha-band (10 Hz) sine wave at `alpha_amp` amplitude added to every
        channel, ensuring non-trivial spectral peaks so band-power and aperiodic
        features are non-NaN and non-trivial.

    Uses mne.RawArray.export(..., fmt='edf') with the edfio backend (installed
    alongside mne). This exercises the real EDF serialization / deserialization
    path rather than bypassing it with a RawArray.
    """
    import mne
    import numpy as np

    rng = np.random.default_rng(seed)
    n_samples = int(math.ceil(duration_s * sfreq))
    n_ch = len(ch_names)

    # White noise base
    raw_noise = rng.normal(0, 1.0, (n_ch, n_samples))

    # Simple low-pass approximation: cumsum & rescale (pink-ish)
    pink = np.cumsum(raw_noise, axis=1)
    pink -= pink.mean(axis=1, keepdims=True)
    pink /= (pink.std(axis=1, keepdims=True) + 1e-12)
    pink *= 1e-5  # ~10 µV RMS

    # Alpha oscillation
    t = np.arange(n_samples) / sfreq
    alpha = alpha_amp * np.sin(2 * np.pi * 10.0 * t)  # 10 Hz

    data = pink + alpha[np.newaxis, :]  # broadcast over channels

    info = mne.create_info(ch_names=ch_names, sfreq=sfreq, ch_types="eeg")
    raw = mne.io.RawArray(data, info, verbose=False)
    raw.export(path, fmt="edf", verbose=False)


def _make_manifest_entry(recording_id: str, patient_id: str, hospital: str,
                         age: float, sfreq: float, filename: str) -> dict:
    return {
        "recording_id": recording_id,
        "patient_id": patient_id,
        "hospital": hospital,
        "age": age,
        "sex": "M",
        "sampling_rate": sfreq,
        "file": filename,
    }


# ---------------------------------------------------------------------------
# Stub embedder (replaces CBraMod/torch)
# ---------------------------------------------------------------------------

class StubEmbedder:
    """Deterministic fixed random-projection embedder.

    Stands in for the frozen CBraMod forward pass which requires torch and the
    real checkpoint weights -- neither is available in this environment. The
    projection matrix is seeded once at construction time, so embedding output
    is fully reproducible given the same input windows.

    Interface matches FrozenEmbedder.embed_windows:
        windows: (n_windows, n_channels, n_samples) float32 ndarray
        returns: (n_windows, d) float32 ndarray  (d=8 by default)
    """

    def __init__(self, d_out: int = 8, seed: int = 99):
        import numpy as np
        self._d_out = d_out
        self._rng = np.random.default_rng(seed)
        self._proj: "np.ndarray | None" = None

    def _get_proj(self, d_in: int) -> "np.ndarray":
        import numpy as np
        if self._proj is None or self._proj.shape[0] != d_in:
            rng = np.random.default_rng(99)
            self._proj = rng.standard_normal((d_in, self._d_out)).astype("float32")
            self._proj /= (np.linalg.norm(self._proj, axis=0, keepdims=True) + 1e-10)
        return self._proj

    def embed_windows(self, windows: "np.ndarray") -> "np.ndarray":
        """Project flattened windows to d_out dimensions."""
        import numpy as np
        w = np.asarray(windows, dtype="float32")
        n_win, n_ch, n_samp = w.shape
        flat = w.reshape(n_win, n_ch * n_samp)  # (n_win, d_in)
        proj = self._get_proj(flat.shape[1])
        return (flat @ proj).astype("float32")  # (n_win, d_out)


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

@unittest.skipUnless(HAVE_STACK, "mne/numpy/sklearn not installed")
class TestLocalEDFIntegration(unittest.TestCase):
    """End-to-end test: real .edf files -> harmonize -> stub embed -> Phase-1."""

    # Channels from base_cfg -- keep the list short (4 ch) for speed.
    CH_NAMES = ["Fp1", "Fp2", "C3", "C4"]
    SFREQ = 200.0
    DURATION_S = 45.0   # 45 s yields one clean 30-s window after harmonization

    def setUp(self):
        """Write 4 real .edf recordings to a temp dir and build the full config.

        We use 2 recordings per discovery site (MGH x2, BWH x2) so that the
        site-probe's 2-fold stratified CV always has at least one sample from
        each hospital in both the train and test splits.
        """
        self._tmp = tempfile.mkdtemp()
        self._artifacts = tempfile.mkdtemp()
        self._logs = tempfile.mkdtemp()

        # Synthesize 4 recordings: 2 from MGH, 2 from BWH.
        recordings_meta = [
            ("rec001", "pt001", "MGH", 45.0, 0),
            ("rec002", "pt002", "MGH", 52.0, 1),
            ("rec003", "pt003", "BWH", 38.0, 2),
            ("rec004", "pt004", "BWH", 61.0, 3),
        ]
        self._manifest = []
        for rec_id, pat_id, hospital, age, seed in recordings_meta:
            fname = f"{rec_id}.edf"
            fpath = os.path.join(self._tmp, fname)
            _write_edf(fpath, self.CH_NAMES, self.SFREQ, self.DURATION_S, seed=seed)
            self._manifest.append(
                _make_manifest_entry(rec_id, pat_id, hospital, age, self.SFREQ, fname)
            )

        self.cfg = _make_cfg(
            artifacts_dir=self._artifacts,
            log_dir=self._logs,
            edf_dir=self._tmp,
            recordings=self._manifest,
        )

    def tearDown(self):
        import shutil
        for d in (self._tmp, self._artifacts, self._logs):
            shutil.rmtree(d, ignore_errors=True)

    # -- sub-tests ----------------------------------------------------------

    def test_edf_files_exist_on_disk(self):
        """Sanity: all synthesized .edf files are readable by mne."""
        import mne
        for entry in self._manifest:
            path = os.path.join(self._tmp, entry["file"])
            self.assertTrue(os.path.isfile(path), f"EDF not found: {path}")
            raw = mne.io.read_raw_edf(path, preload=False, verbose=False)
            self.assertEqual(sorted(raw.ch_names), sorted(self.CH_NAMES))

    def test_local_edf_client_lists_recordings(self):
        """LocalEDFClient.list_recordings yields correct RecordingRefs per hospital."""
        from pipeline.stream_fetch import LocalEDFClient

        client = LocalEDFClient(self.cfg)
        mgh_refs = list(client.list_recordings("MGH"))
        bwh_refs = list(client.list_recordings("BWH"))
        self.assertEqual(len(mgh_refs), 2)
        self.assertEqual(len(bwh_refs), 2)
        for ref in mgh_refs + bwh_refs:
            self.assertIsNotNone(ref.uri)
            self.assertTrue(os.path.isabs(ref.uri), f"URI should be absolute: {ref.uri}")
            self.assertTrue(os.path.isfile(ref.uri), f"URI file missing: {ref.uri}")
        self.assertEqual(bwh_refs[0].hospital, "BWH")

    def test_open_stream_returns_mne_raw_and_does_not_delete_file(self):
        """open_stream returns a lazy mne Raw; the source file survives context exit."""
        from pipeline.stream_fetch import LocalEDFClient, open_recording

        client = LocalEDFClient(self.cfg)
        refs = list(client.list_recordings("MGH"))
        ref = refs[0]
        original_path = ref.uri

        self.assertTrue(os.path.isfile(original_path))
        with open_recording(self.cfg, ref, client) as raw:
            self.assertIsNotNone(raw)
            self.assertIn("Fp1", raw.ch_names)
        # File must NOT be deleted (it's the user's own EDF, not a scratch fetch).
        self.assertTrue(
            os.path.isfile(original_path),
            f"Source EDF was unexpectedly deleted: {original_path}",
        )

    def test_full_pipeline_run_pass1(self):
        """run_pass1.run() processes all 3 EDF recordings end-to-end.

        Checks:
          * one compact row per eligible recording (all 3 pass age >= 18)
          * each row has an embedding vector and a features dict
          * REAL band-power and aperiodic features are finite (non-NaN) floats
        """
        from pipeline.run_pass1 import run
        from pipeline.stream_fetch import LocalEDFClient
        from pipeline.writer import CompactTableWriter, load_compact_tables

        client = LocalEDFClient(self.cfg)
        embedder = StubEmbedder(d_out=8)

        with CompactTableWriter(self.cfg, backend="jsonl") as writer:
            result = run(self.cfg, writer, embedder=embedder, client=client)
            writer.flush()

        self.assertEqual(result["n_written"], 4,
                         f"Expected 4 written rows, got {result['n_written']}")

        tables = load_compact_tables(self.cfg)
        self.assertEqual(len(tables["recording_id"]), 4)

        for rid, emb, feat, qc in zip(
            tables["recording_id"],
            tables["embedding"],
            tables["features"],
            tables["qc"],
        ):
            with self.subTest(recording_id=rid):
                # Embedding vector must be a non-empty list of floats.
                self.assertIsInstance(emb, list)
                self.assertGreater(len(emb), 0)
                self.assertTrue(all(isinstance(v, float) for v in emb),
                                "embedding values should all be float")

                # Features dict: spot-check REAL DSP outputs.
                self.assertIn("bp_alpha_Fp1", feat,
                              "alpha band-power key missing")
                self.assertIn("aperiodic_exponent_Fp1", feat,
                              "aperiodic exponent key missing")

                bp_alpha = feat["bp_alpha_Fp1"]
                ap_exp = feat["aperiodic_exponent_Fp1"]

                self.assertIsInstance(bp_alpha, float, "bp_alpha_Fp1 is not float")
                self.assertIsInstance(ap_exp, float, "aperiodic_exponent_Fp1 is not float")

                self.assertFalse(math.isnan(bp_alpha),
                                 f"bp_alpha_Fp1 is NaN for {rid}")
                self.assertFalse(math.isinf(bp_alpha),
                                 f"bp_alpha_Fp1 is Inf for {rid}")
                self.assertFalse(math.isnan(ap_exp),
                                 f"aperiodic_exponent_Fp1 is NaN for {rid}")
                self.assertFalse(math.isinf(ap_exp),
                                 f"aperiodic_exponent_Fp1 is Inf for {rid}")

                # QC table must have hospital and sampling_rate but NOT embedding/features.
                self.assertIn("hospital", qc)
                self.assertIn("sampling_rate", qc)
                self.assertNotIn("embedding", qc,
                                 "embedding must not appear in qc table")
                self.assertNotIn("features", qc,
                                 "features must not appear in qc table")

    def test_feature_values_are_non_trivial(self):
        """After processing, check example feature values are physically reasonable.

        The synthesized signal has:
          - A 10 Hz sine wave at ~30 µV peak amplitude -> alpha band power > 0
          - Pink-ish noise background -> aperiodic exponent > 0 (positive slope)

        We don't gate on exact numbers (DSP parameters vary), but we assert that
        the features are positive and in a plausible range.
        """
        from pipeline.run_pass1 import run
        from pipeline.stream_fetch import LocalEDFClient
        from pipeline.writer import CompactTableWriter, load_compact_tables

        client = LocalEDFClient(self.cfg)
        embedder = StubEmbedder(d_out=8)

        with CompactTableWriter(self.cfg, backend="jsonl") as writer:
            run(self.cfg, writer, embedder=embedder, client=client)
            writer.flush()

        tables = load_compact_tables(self.cfg)
        # Pick the first row.
        feat = tables["features"][0]

        bp_alpha = feat["bp_alpha_Fp1"]
        bp_delta = feat["bp_delta_Fp1"]
        ap_exp = feat["aperiodic_exponent_Fp1"]

        # Alpha band power must be positive (we injected an alpha oscillation).
        self.assertGreater(bp_alpha, 0.0,
                           f"alpha band power should be > 0, got {bp_alpha}")
        # Delta power must also be positive (noise has low-frequency content).
        self.assertGreater(bp_delta, 0.0,
                           f"delta band power should be > 0, got {bp_delta}")
        # Aperiodic exponent: real EEG has 1/f spectrum, so exponent > 0.
        # (Our pink-ish noise has a positive slope in log-log PSD.)
        self.assertGreater(ap_exp, 0.0,
                           f"aperiodic exponent should be > 0 for 1/f noise, got {ap_exp}")

        # Print a couple of representative values for the run report.
        print(f"\n[feature values from rec001] "
              f"bp_alpha_Fp1={bp_alpha:.4e}, "
              f"bp_delta_Fp1={bp_delta:.4e}, "
              f"aperiodic_exponent_Fp1={ap_exp:.4f}")

    def test_phase1_analysis_on_real_features(self):
        """Run Phase-1 analysis on compact tables built from real EDF signal.

        With only 3 recordings we cannot expect meaningful clustering, but the
        full analysis chain (site correction, PAC k selection, phenotype bar,
        negative control) must complete and return the required keys.

        We do NOT assert specific k or gate pass (3 samples cannot satisfy the
        site-probe's cross-validation), but we assert the structural keys are
        present in the report.
        """
        from analysis.run_phase1 import run_phase1
        from pipeline.run_pass1 import run
        from pipeline.stream_fetch import LocalEDFClient
        from pipeline.writer import CompactTableWriter, load_compact_tables

        client = LocalEDFClient(self.cfg)
        embedder = StubEmbedder(d_out=8)

        with CompactTableWriter(self.cfg, backend="jsonl") as writer:
            run(self.cfg, writer, embedder=embedder, client=client)
            writer.flush()

        tables = load_compact_tables(self.cfg)

        # run_phase1 requires site_invariance config; use minimal cv_folds=2
        # (already set in setUp via _make_cfg). With 3 samples the site probe
        # may fail, but the chain must not raise.
        try:
            report = run_phase1(self.cfg, tables)
        except Exception as exc:
            self.fail(f"run_phase1 raised unexpectedly: {exc}")

        # Structural keys that must always be present.
        self.assertIn("k_selected", report,
                      "report missing 'k_selected'")
        self.assertIn("phenotype_bar", report,
                      "report missing 'phenotype_bar'")
        self.assertIn("negative_control_surrogate", report,
                      "report missing 'negative_control_surrogate'")

        self.assertIsInstance(report["k_selected"], int)
        self.assertIsInstance(report["phenotype_bar"], dict)
        self.assertIsInstance(report["negative_control_surrogate"], dict)

        print(f"\n[Phase-1 report] k_selected={report['k_selected']}, "
              f"n_admitted={report['phenotype_bar'].get('n_admitted')}, "
              f"negative_control={report['negative_control_surrogate']}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
