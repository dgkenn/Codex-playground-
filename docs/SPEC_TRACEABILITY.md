# Spec Traceability Matrix

This document maps each binding integrity rule from the v2 pre-registration spec
("Unsupervised Raw-Waveform EEG Phenotype Discovery on HEEDB via an Adapted
Foundation Model -- Pre-Registration + Execution Spec v2") to the specific
symbols in this repository that enforce it. Its purpose is to let an auditor
verify that the pre-registration commitments are structurally enforced in code,
not merely stated in comments.

---

## The four frozen objects (Sec 3)

Before the held-out hospital is unlocked the following four objects must be
frozen and hash-verified. Their hashes are assembled into a manifest by
`phase2/freeze.build_manifest` and written to the path named by
`config.yaml::frozen_manifest` (`artifacts/frozen/manifest.json`). The
`HeldoutGuard.unlock_held_out` method refuses to proceed unless all four keys
are present and none contains a TO-CONFIRM placeholder.

| Frozen object | What is hashed | Hash produced by | Stored in manifest as |
|---|---|---|---|
| Model checkpoint | Binary checkpoint file (SHA-256, streamed in 1 MiB chunks) | `common/hashing.hash_file` called inside `pipeline/embed.FrozenEmbedder.load`; expected value read from `config.yaml::model.checkpoint_sha256` | `checkpoint_sha256` |
| Harmonization + model-IO config | Canonical JSON of the `model` I/O fields + `harmonization` + `embedding` sub-dicts from config | `common/config.harmonization_hash`; each individual `HarmonizationPlan` instance also exposes `pipeline/harmonize.HarmonizationPlan.content_hash` (hashes `__dict__`) and is stamped per-row in the embedding table | `harmonization_hash` |
| Embedding-correction transform | Canonical JSON of the fitted ComBat parameters (`grand_mean`, `pooled_std`, `gamma`, `delta`, `batches`) | `analysis/correct_sites.SiteCorrection.content_hash` | `correction_transform_hash` |
| Phenotype-assignment function | Canonical JSON of the GMM parameters (`k`, `means`, `weights`, `covariance_type`), rounded to 6 d.p. | `analysis/cluster.PhenotypeAssigner.content_hash` | `assignment_fn_hash` |

`phase2/freeze.build_manifest` receives the checkpoint hash and the two
analysis-object hashes as arguments, calls `common/config.harmonization_hash`
itself for the harmonization hash, and returns the complete manifest dict.
`phase2/freeze.write_manifest` persists it and appends the combined
frozen-pipeline hash (hash of the manifest dict itself) to
`artifacts/logs/freeze.log`.

---

## Binding integrity rules -> enforcement

| Rule (from spec) | Spec S | Enforced by (file:symbol) | Test |
|---|---|---|---|
| Phase-1 firewall: held-out site hard-blocked while phase == 1 | 0, 6 | `guards/heldout_guard.HeldoutGuard.check_site_access` -- raises `FirewallBreach` if `phase == 1` and `site == held_out`; every attempt (blocked or not) is appended to `artifacts/logs/firewall.log` via `common/logging_utils.audit_log` | `tests/test_integrity.py::TestFirewall.test_phase1_blocks_heldout`, `test_block_is_logged` |
| No outcome variable importable into Phase-1 workspace | 0, 13 | `common/config.assert_no_outcome_in_loader_fields` -- rejects any field whose lowercased name appears in `_OUTCOME_KEYS` (`outcome`, `label`, `y`, `target`, `icd`, `icd10`, `medication`, `medications`, `report_text`, `mortality`, `seizure_label`); `pipeline/stream_fetch.RecordingRef` carries EEG-acquisition metadata only by design | `tests/test_integrity.py::TestConfigInvariants.test_no_outcome_fields_in_phase1_loader` |
| Held-out hospital not in discovery set | 6 | `common/config.validate` -- raises `ConfigError` if `sites.held_out in sites.discovery`; `guards/heldout_guard.HeldoutGuard.__init__` raises `FirewallBreach` on the same condition at runtime | `tests/test_integrity.py::TestConfigInvariants.test_held_out_cannot_be_in_discovery` |
| Single-test / run-once design | 2, 12, 14 | `phase2/unlock_and_test._acquire_run_once` -- creates `artifacts/phase2/RUN_ONCE.lock` with `O_CREAT | O_EXCL`; any subsequent call raises `RunOnceViolation`; acquired by `phase2/run_phase2.run_phase2` right after unlock; `common/config.validate` requires `phase2.run_once == True` | `tests/test_integrity.py::TestRunOnceLock.test_second_test_aborts`, `tests/test_phase2_e2e.py` (second call aborts), `TestConfigInvariants.test_run_once_required` |
| Unlock requires phase == 2 and a complete, placeholder-free manifest | 3 | `guards/heldout_guard.HeldoutGuard.unlock_held_out` -- checks `phase == 2`, then checks all four required manifest keys are present, then checks none starts with `"TO-CONFIRM"`; passes if and only if all three conditions hold | `tests/test_integrity.py::TestFirewall.test_unlock_requires_phase2`, `test_unlock_rejects_incomplete_manifest`, `test_unlock_rejects_placeholder`, `test_unlock_succeeds_and_stamps_hash` |
| Deterministic, order-independent content hashing | 0, 3 | `common/hashing.canonical_json` (sorted keys, no insignificant whitespace) + `hash_bytes`; `hash_file` streams in 1 MiB chunks; `hash_object` composes both | `tests/test_integrity.py::TestHashing.test_canonical_json_is_order_independent`, `test_hash_object_stable_and_sensitive`, `test_verify_object`, `test_hash_file_streaming` |
| Disk-sparing single streaming pass; raw never persisted beyond the with-block | 0 | `pipeline/stream_fetch.open_recording` context manager -- on exit calls `raw.close()` and, in `batch_and_delete` mode, calls `shutil.rmtree` on the shard directory before the next shard is fetched; `pipeline/run_pass1.run` enforces `phase == 1` and passes each recording through `open_recording` | `tests/test_integrity.py::TestDiskSparingBookkeeping.test_shard_iter` (structural); the context-manager cleanup path requires I/O integration |
| Shard + checkpoint + resume | 0 | `pipeline/run_pass1.load_completed` / `mark_completed` -- maintain an append-only text file at `artifacts/pass1_done.txt`; `run` skips any `recording_id` already in that set and calls `writer.flush()` after each shard | `tests/test_integrity.py::TestDiskSparingBookkeeping.test_resume_set_roundtrip` |
| Site-invariance gate: site identity near chance after correction (AUC <= tolerance) | 8 | `analysis/site_probe.probe_site` -- fits a stratified k-fold logistic regression on the corrected embeddings for each of `hospital`, `device`, and `sampling_rate`; returns `{"pass": auc <= chance_tolerance_auc}`; tolerance is read from `config.yaml::site_invariance.site_probe.chance_tolerance_auc` (default 0.58) | `tests/test_analysis.py::TestSiteCorrectionGate.test_correction_reduces_site_predictability` |
| Stability-based k selection -- never interpretability | 9 | `analysis/cluster.consensus_pac` computes PAC per candidate k; `analysis/cluster.select_k` picks the k minimising PAC; interpretability of the clusters plays no role in this selection | `tests/test_analysis.py::TestConsensusClustering.test_pac_recovers_planted_k` |
| Cross-site reproducibility ARI gate (provisional → confirmed) | 6, 9 | `analysis/cluster.cross_site_reproducibility` applies the frozen assigner to the held-out site vs an independently re-derived clustering (`ari >= reproducibility_ari_threshold`); `phase2/run_phase2.run_phase2` runs this on unlock (EEG only) and only proceeds to the outcome test if the primary phenotype passes | `tests/test_phase2_e2e.py::TestPhase2EndToEnd.test_happy_path_then_run_once` |
| The "real phenotype" bar -- stability AND site-audit AND cross-site | 9 | `analysis/phenotype_bar.apply_phenotype_bar` combines resampling stability, per-cluster site-alignment (`per_cluster_site_alignment`), and LOSO; Phase 1 caps at `provisional` (held-out locked), promoted to `confirmed` only by the held-out ARI in Phase 2 | `tests/test_integrity.py::TestPhenotypeBar` (status logic); `tests/test_pipeline_e2e.py::TestPhase1EndToEnd` (provisional ceiling) |
| Negative controls must fail (structure collapses under surrogates; association collapses under shuffled outcome) | 11, 13, 17 | `analysis/audits.phase_randomized_surrogate` + `clustering_structure_score` + `surrogate_structure_collapse`, wired into `analysis/run_phase1.run_phase1` so every candidate solution is refuted against surrogates; `analysis/audits.negative_control_shuffled_outcome` runs in `phase2/run_phase2.run_phase2` after the outcome test | `tests/test_analysis.py::TestNegativeControls`; `tests/test_pipeline_e2e.py` (Phase-1 wiring); `tests/test_phase2_e2e.py` (leakage control) |
| Frozen-pipeline hash verified before unlock | 3 | `phase2/run_phase2.run_phase2` recomputes `hash_object(manifest)` and compares to `expected_pipeline_hash`, raising `FirewallBreach` before `guard.unlock_held_out`; also `phase2/unlock_and_test.run` | `tests/test_phase2_e2e.py::test_firewall_gates_trip_before_unlock` (wrong-hash case) |
| Frozen OBJECTS re-verified before unlock (no peeking re-fit) | 3 | `phase2/run_phase2._verify_frozen_objects` re-hashes the live `SiteCorrection` and `PhenotypeAssigner` and raises `FirewallBreach` unless they equal `manifest["correction_transform_hash"]` / `["assignment_fn_hash"]` | `tests/test_phase2_e2e.py::test_firewall_gates_trip_before_unlock` (tampered-object case) |
| Temporal precedence (EEG before outcome) required | 5, 12, 13 | `phase2/run_phase2.run_phase2` refuses to run unless the loader passes `temporal_precedence_verified=True` | `tests/test_phase2_e2e.py::test_firewall_gates_trip_before_unlock` (precedence case) |

---

## Disk-sparing guarantees (Sec 0)

- **Raw never persisted.** `pipeline/stream_fetch.open_recording` is a context
  manager. In `stream` mode the lazy reader is closed on exit. In
  `batch_and_delete` mode the shard directory is removed with `shutil.rmtree`
  in the `finally` block before the next shard is requested. Neither mode
  leaves raw signal on disk after the `with` block completes.

- **One shard at a time.** `pipeline/run_pass1.shard_iter` yields batches of
  at most `execution.shard_size_recordings` (default 500) recordings. The
  orchestrator (`run_pass1.run`) processes and flushes one shard before
  advancing. The scratch directory (`data.scratch_dir`) therefore holds at most
  one shard's worth of raw at any instant.

- **Compact-only outputs.** The only artifacts written to disk by Pass 1 are
  the compact embedding table, feature table, and QC table (Parquet/Zarr via
  the injected `writer`), plus the append-only resume file
  (`artifacts/pass1_done.txt`) and structured log lines. No intermediate
  windowed arrays are persisted; epoch-level embeddings are kept only for a
  2% random subsample (`embedding.persist_epoch_subset_fraction`), selected
  deterministically by `pipeline/embed.should_keep_epoch_subset` (hash-based,
  resume-safe).

- **Resumability.** `pipeline/run_pass1.load_completed` reads the resume set
  from `artifacts/pass1_done.txt` at startup. `mark_completed` appends one line
  per recording after its compact row is written. If the process is interrupted
  the next invocation skips already-completed recordings.

- **Lazy heavy imports.** `mne`, `torch`, `numpy`, `scipy`, `sklearn`, and
  `statsmodels` are all imported inside function bodies, not at module level.
  This keeps the integrity and config layers (which are exercised by stdlib-only
  tests) free of scientific-stack dependencies.

---

## Adapter boundaries (not yet wired)

The following three symbols raise `NotImplementedError` and are the **only**
site- or model-specific I/O seams in the pipeline. Everything else is pure
logic that runs without credentials or a GPU.

| Symbol | File | What to wire |
|---|---|---|
| `_BDSPClient.list_recordings(hospital)` | `pipeline/stream_fetch.py` | Return an iterable of `RecordingRef` objects from the credentialed BDSP catalog for the given hospital. Must include acquisition metadata only (no outcome fields). |
| `_BDSPClient.open_stream(ref)` | `pipeline/stream_fetch.py` | Return a lazy raw reader (e.g. `mne.io.Raw` with `preload=False`) for the recording described by `ref`. |
| `_BDSPClient.download_shard(refs, dest)` | `pipeline/stream_fetch.py` | Download a batch of recordings to `dest` and return the shard directory path (used only in `batch_and_delete` mode). |
| `FrozenEmbedder.load(checkpoint_path)` | `pipeline/embed.py` | After hash verification passes, construct the architecture named in `cfg.model.name`, call `load_state_dict` from the verified checkpoint, set `model.eval()`, and freeze all parameters (`requires_grad=False`). |
| `FrozenEmbedder.embed_windows(windows)` | `pipeline/embed.py` | Run the frozen forward pass on a `(n_windows, n_channels, n_samples)` array and return `(n_windows, d)`. The `@torch_inference` decorator wraps the call in `torch.no_grad`. The body currently defers to `self.model(x)` after the `NotImplementedError` in `load` is resolved. |
| `_load_frozen_assigner(cfg, manifest)` | `phase2/unlock_and_test.py` | Deserialize the frozen `PhenotypeAssigner`, call `assigner.content_hash()`, and verify it equals `manifest["assignment_fn_hash"]` before returning. |

These six methods are the **only** site/model-specific I/O seams. All other
pipeline logic is wired and unit-tested.

---

## TO-CONFIRM parameters

`config.yaml` uses the marker `TO-CONFIRM` for every parameter that corresponds
to a `[fill]` slot in the v2 spec -- values that must be pinned to a concrete
value and the config re-hashed before the relevant stage may run.

Current TO-CONFIRM slots and where each is consumed:

| Parameter path | Consumed by |
|---|---|
| `cohort.qc.min_recording_seconds` | `pipeline/stream_fetch.iter_qualifying_recordings` (QC gate) |
| `cohort.qc.max_bad_channel_fraction` | QC gate |
| `cohort.qc.max_flatline_fraction` | QC gate |
| `sites.discovery` | `guards/heldout_guard.HeldoutGuard`, `pipeline/stream_fetch.iter_qualifying_recordings` |
| `sites.held_out` | `guards/heldout_guard.HeldoutGuard` (firewall identity) |
| `sites.reproducibility_ari_threshold` | `analysis/cluster.cross_site_reproducibility` |
| `data.version` | BDSP catalog query (adapter boundary) |
| `model.repo_id` | `pipeline/embed.FrozenEmbedder.load` (adapter boundary) |
| `model.revision` | `pipeline/embed.FrozenEmbedder.load` |
| `model.checkpoint_sha256` | `pipeline/embed.FrozenEmbedder.load` (hash gate); `phase2/freeze.build_manifest` |
| `model.expected_sfreq_hz` | `pipeline/harmonize.plan_harmonization` |
| `model.window_seconds` | `pipeline/harmonize.plan_harmonization` |
| `harmonization.reference` | `pipeline/harmonize.plan_harmonization` |
| `harmonization.bandpass_hz` | `pipeline/harmonize.plan_harmonization` |
| `harmonization.artifact_reject_z` | `pipeline/harmonize._window_and_reject` |
| `site_invariance.site_probe.chance_tolerance_auc` | `analysis/site_probe.probe_site` (gate threshold) |
| `clustering.stability_min` | `analysis/cluster.stability_score` (admission bar) |
| `phase2.outcome` | `phase2/unlock_and_test.run` (single pre-registered outcome) |
| `phase2.primary_phenotype` | `phase2/unlock_and_test._primary_phenotype_id` |
| `phase2.association_criterion.min_effect_size_or` | `phase2/unlock_and_test.adjusted_association` |
| `phase2.min_evaluable_heldout_n` | Evaluated before unlock |

`guards/heldout_guard.HeldoutGuard.unlock_held_out` explicitly rejects a
manifest whose hash fields start with `"TO-CONFIRM"` (case-insensitive prefix
check), so the firewall structurally prevents unlock until all four frozen
hashes have been pinned to real values.
