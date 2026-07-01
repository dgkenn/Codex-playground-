# LESSONS — durable, accumulating research memory (read FIRST every cycle; append after every experiment)

Format: each lesson = what we learned + the mechanism + the implication. Negative results are first-class.

## Data access & environment
- **BDSP/HEEDB creds:** the valid credential is the `[physionet]` AWS profile in `~/.aws/credentials`.
  Invalid `AWS_ACCESS_KEY_ID`/`SECRET` env vars SHADOW it (boto3 puts env ahead of profiles). Always run
  BDSP work with `env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY -u AWS_SESSION_TOKEN` + profile=physionet.
- **`config.yaml` catalog_key** `HEEDB/index.tsv` is stale (404); real catalog is `EEG/eeg-metadata/<SITE>_*.csv`.
- **Shell heredocs (`cat <<EOF`) FAIL** in this environment's bash wrapper (silent exit 1 → scripts never
  written → "silent hangs"). ALWAYS create scripts with the Write tool, not heredocs.
- **Container reaps on inactivity** → commit + push every cycle; keep raw data in scratchpad only.
- **eICU/PhysioNet** reachable via `~/.netrc` (`wget --netrc`, not curl). MIMIC-IV + eICU + VitalDB + INSPIRE all accessible.

## EEG / foundation-model pipeline (validated)
- **CBraMod weights:** `weighting666/CBraMod/pretrained_weights.pth` (19.8MB), sha256 matches the repo pin;
  loads into `braindecode.models.CBraMod(n_outputs, n_chans=19, sfreq=200, n_times=6000, patch_size=200,
  return_encoder_output=True)` with 0 missing keys. Forward pass validated on real HEEDB EDF.
- **SCALING BUG (critical):** mne reads EDF in VOLTS (~5e-5); CBraMod expects **µV** → multiply by 1e6.
  Per-channel z-norm DESTROYS the amplitude scale → uninformative embeddings. µV scaling took within-site
  abnormal-EEG AUC 0.40 → 0.62.
- **Representation ceiling (failure analysis, n=89):** frozen **mean-pooled** embedding is LOW-RANK and
  AMPLITUDE-DOMINATED (PC1 = 67% var ~ amplitude; 3 PCs = 90% var). OOF AUC ~0.5 while in-sample = 1.0;
  flat across all PCA dims and regularization → NOT fixable by shrinkage. Mean-pooling washes out the
  localized/transient graphoelements that define abnormality. **Implication:** frozen mean-pool is the
  wrong representation; need **full-token attention/MIL head + encoder fine-tuning + large n → GPU.**
- **Compute:** CPU is impractical for EEG foundation-model embedding/fine-tuning at scale (repo's embed.py
  says so explicitly). Queue EEG-DL work for GPU; use CPU for tabular ML, data eng, red-team, validation.

## Methodological lessons (from killed/incremental findings)
- **Named-index trap:** "vasopressor dose → mortality" IS the VIS/VDI/BPRI literature → desk-reject. HPI
  is a live named-index controversy. Novelty must not map to an existing named score.
- **Confounding-by-indication caps treatment-decision questions.** Liberation-order → mortality (OR 1.35,
  E-value 1.83) and dose→mortality attenuate to "sicker patients"; severity-at-decision is under-measured.
- **"Trait" claims need cross-encounter test-retest.** Vasopressor "requirement" reliability 0.95 was
  within-encounter autocorrelation; cross-encounter ICC = 0.07 → NOT a stable trait.
- **External validation is the bar.** Delirium model derivation AUC 0.90 → MIMIC 0.58 (transport failure);
  clean transportable clinical features only ~0.62 cross-hospital (documentation-burden count inflates to
  0.82 but is ascertainment-confounded).
- **Watch p>>n variance:** in-sample AUC 1.0 + OOF 0.5 = memorization, not signal.
- **Negative-control calibration (Schuemie/Madigan)** kills spurious causal claims; **E-value** bounds
  unmeasured confounding; **landmark design** defeats immortal-time; **ascertainment/documentation** features leak.
- **Occult-dependence-at-normal-pressure (ICU):** survived hardening (MICE OR 2.04, collider test passed)
  but INCREMENTAL — the novel "at-target" conditioning added only +0.03 AUC; "gap doubles" was 72% a
  MAP restriction-of-range artifact. Real, not top-tier.

## Process lessons (how the machine must operate)
- **Hostile-review is a mandatory GATE, not a step.** Nothing is a finding until it survives an aggressive
  multi-lens panel (stats/overfit, causal/confounding, novelty/prior-art, external validity, independent
  reproduction, and a "collapse-to-known+artifact" skeptic) + external validation. **Log every attack and
  its outcome into this file** — the attack→result map is the most valuable memory (it stops repeat
  mistakes and makes us harder to fool). Scale rounds to ambition (top-tier claim → 3–5 rounds).
- **CPU-overnight is enough for a real EEG result via the frozen path** (updates the "GPU-gated" view):
  overnight, precompute frozen CBraMod PER-WINDOW embeddings for thousands of patients (~1 patient/10 s
  incl. download), then train a SMALL attention/MIL head over the cached embeddings on CPU. This avoids
  the mean-pool ceiling (attend over windows) AND the GPU need. Only end-to-end encoder fine-tuning
  remains GPU-only. Checkpoint every N patients (reaps).

## Open opportunity (the current best shot)
- **No EEG foundation model has been applied to clinical/neuro outcome prediction with external validation
  anywhere (as of 2026)** — DELPHI-EEG is single-center. HEEDB (multi-site EEG + ICD10/OMOP outcomes +
  DateOfDeath) enables the first cross-site-validated EEG-foundation-model outcome study. Pipeline
  validated, preprocessing solved (µV). Now approachable on CPU overnight via the frozen-embedding + MIL-
  head path (see process lesson above); encoder fine-tuning deferred to a future GPU env.
