"""End-to-end test: compact-table writer -> Phase-1 analysis orchestrator.

Builds synthetic compact rows with (a) a planted 3-cluster phenotype structure in
the embedding and (b) a strong additive per-site offset overlaid on it -- exactly
the confound the pipeline must remove. Then it writes the rows through
CompactTableWriter, reads them back, and runs the full Phase-1 chain, asserting:

  * the writer fans one row into three aligned tables and round-trips them;
  * after site correction the site-probe GATE passes (offset removed);
  * stability-based k selection recovers the planted k = 3;
  * the phenotype bar admits provisional phenotypes (Phase-1 ceiling);
  * a JSON report is written.

Skipped automatically without numpy/scikit-learn.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import numpy as np  # noqa: F401
    import sklearn  # noqa: F401
    HAVE_STACK = True
except ImportError:
    HAVE_STACK = False

from tests.test_integrity import base_cfg


def _synthetic_tables(n_per_cluster=60, d=16, seed=0):
    """Three blobs in embedding space, each split across two discovery sites with
    a large site-specific additive offset (the confound to be corrected out)."""
    import numpy as np

    rng = np.random.default_rng(seed)
    centers = np.array([[0.0] * d, [8.0] * d, [0.0] * (d // 2) + [8.0] * (d - d // 2)])
    site_offset = {"MGH": np.full(d, 5.0), "BWH": np.full(d, -5.0)}
    rows = []
    rid = 0
    for c, ctr in enumerate(centers):
        for k in range(n_per_cluster):
            site = "MGH" if k % 2 == 0 else "BWH"
            emb = ctr + rng.normal(scale=0.4, size=d) + site_offset[site]
            rows.append({
                "recording_id": f"rec{rid}",
                "patient_id": f"p{rid}",
                "hospital": site,
                "device": f"dev_{site}",
                "sampling_rate": 200.0,
                "recording_length": 600.0,
                "embedding": emb.tolist(),
                "features": {"bp_alpha_C3": float(emb[0]),
                             "aperiodic_exponent_C3": float(c)},
                "n_windows": 20,
                "harmonization_hash": "h",
                "keep_epoch_subset": False,
            })
            rid += 1
    rng.shuffle(rows)
    return rows


@unittest.skipUnless(HAVE_STACK, "numpy/sklearn not installed")
class TestWriterRoundTrip(unittest.TestCase):
    def test_fan_out_and_realign(self):
        from pipeline.writer import CompactTableWriter, load_compact_tables

        cfg = base_cfg()
        cfg["artifacts_dir"] = tempfile.mkdtemp()
        rows = _synthetic_tables(n_per_cluster=5, d=4)
        w = CompactTableWriter(cfg, backend="jsonl")
        for i, r in enumerate(rows):
            w.write_row(r)
            if i % 4 == 3:
                w.flush()          # multiple shard fragments
        w.close()

        t = load_compact_tables(cfg)
        self.assertEqual(len(t["recording_id"]), len(rows))
        # Embedding, features, qc all aligned by recording_id.
        for rid, emb, feat, qc in zip(t["recording_id"], t["embedding"],
                                      t["features"], t["qc"]):
            self.assertEqual(feat["recording_id"], rid)
            self.assertEqual(qc["recording_id"], rid)
            self.assertEqual(len(emb), 4)
            self.assertNotIn("embedding", qc)   # raw split out of qc table


@unittest.skipUnless(HAVE_STACK, "numpy/sklearn not installed")
class TestPhase1EndToEnd(unittest.TestCase):
    def _cfg(self):
        cfg = base_cfg()
        cfg["phase"] = 1
        cfg["artifacts_dir"] = tempfile.mkdtemp()
        cfg["log_dir"] = tempfile.mkdtemp()
        cfg["sites"] = {"discovery": ["MGH", "BWH"], "held_out": "BIDMC",
                        "reproducibility_ari_threshold": 0.5}
        cfg["site_invariance"] = {
            "route_a_method": "combat",
            "site_probe": {"targets": ["hospital"], "classifier": "logreg",
                           "chance_tolerance_auc": 0.65, "cv_folds": 4},
        }
        cfg["clustering"] = {
            "algorithm": "gmm", "k_candidates": [2, 3, 4, 5],
            "k_selection": "consensus_pac", "stability_min": 0.7,
            "consensus": {"n_resamples": 20, "subsample_fraction": 0.8,
                          "pac_low": 0.1, "pac_high": 0.9},
        }
        cfg["audits"] = {"acquisition_covariates": ["sampling_rate", "recording_length"],
                         "site_purity_reject": 0.85}
        return cfg

    def test_full_chain(self):
        from analysis.run_phase1 import run_phase1, write_report
        from pipeline.writer import CompactTableWriter, load_compact_tables

        cfg = self._cfg()
        rows = _synthetic_tables(n_per_cluster=60, d=16, seed=1)
        with CompactTableWriter(cfg, backend="jsonl") as w:
            for r in rows:
                w.write_row(r)
            w.flush()
        tables = load_compact_tables(cfg)

        report = run_phase1(cfg, tables)

        # The site offset was huge; correction must drive the gate to ~chance.
        self.assertTrue(report["site_probe_gate_pass"],
                        f"gate failed: {report['site_probe_gate']}")
        # Planted three clusters recovered by the stability criterion.
        self.assertEqual(report["k_selected"], 3)
        # Phase-1 ceiling: admitted phenotypes are provisional, not confirmed.
        statuses = {d["status"] for d in report["phenotype_bar"]["decisions"].values()}
        self.assertTrue(report["phenotype_bar"]["n_admitted"] >= 1)
        self.assertNotIn("confirmed", statuses)

        path = write_report(cfg, report)
        self.assertTrue(os.path.exists(path))

    def test_held_out_rows_are_refused(self):
        from analysis.run_phase1 import run_phase1
        from guards.heldout_guard import FirewallBreach

        cfg = self._cfg()
        rows = _synthetic_tables(n_per_cluster=10, d=8)
        rows[0]["hospital"] = "BIDMC"          # smuggle in a held-out row
        tables = {"recording_id": [r["recording_id"] for r in rows],
                  "embedding": [r["embedding"] for r in rows],
                  "features": [{"recording_id": r["recording_id"], **r["features"]} for r in rows],
                  "qc": [{k: v for k, v in r.items() if k not in ("embedding", "features")} for r in rows]}
        with self.assertRaises(FirewallBreach):
            run_phase1(cfg, tables)


if __name__ == "__main__":
    unittest.main(verbosity=2)
