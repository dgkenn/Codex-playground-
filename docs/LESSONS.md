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

## Cycle 1 — flagship DESIGN pre-mortem (attack → fix map; hostile-review gate applied BEFORE running)
The naive flagship (frozen embed → MIL head → abnormal-vs-normal EEG, train S0001/test I0002) would FAIL
review. Attacks and the fixes now baked into the design:
- **ATTACK: site = hospital confound / shortcut learning.** Embeddings are amplitude/gross-signal
  dominated (PC1=67% var); a single train-site/test-site split invites "you learned the amplifier."
  **FIX:** run `analysis/site_probe.py` on per-window tokens; fit `analysis/correct_sites.py` Route-A
  site-correction on the TRAIN site only; publish a gate = post-correction site-AUC ≤ chance; test
  bidirectionally AND confirm on a THIRD never-touched site (not S0001↔I0002 ping-pong).
- **ATTACK: abnormal-vs-normal EEG is a SOLVED benchmark (TUAB ~0.90 fine-tuned).** Doing it cross-site
  frozen reads as "reproduced a known task worse on less data." **FIX:** demote abnormal/normal to a
  calibration/sanity check; primary outcome = something with NO existing FM literature.
- **ATTACK: "abnormal" label = one neurologist's gestalt** (reader/site-culture dependent, no inter-rater,
  circular vs the report). **FIX:** use an ICD-coded diagnosis or death — NOT a report-derived bit.
- **REDESIGN (adopted): primary = cognitive/behavioral-syndrome (encephalopathy/delirium-spectrum)
  ICD-10** (`HEEDB_ICD10_for_Neurology.csv`); **secondary = mortality** (DateOfDeath); train-S0001 /
  tune-I0002 / confirm-third-site; site-invariance correction+audit BEFORE the outcome head is trained;
  pre-register via the repo freeze/hash machinery; pre-register an honest sub-SOTA (frozen≠fine-tuned) framing.
- **ATTACK: the mean-pool-ceiling diagnostic was only on POOLED embeddings.** **FIX:** re-run the
  in-sample-vs-OOF / PCA / rank diagnostic at the TOKEN/MIL level before trusting the MIL head escapes it.
- The embedding cache is outcome-AGNOSTIC (per-window EEG reps keyed by site_pid) → reuse it, just re-join
  to the ICD/mortality labels. No re-embedding needed when the outcome changes.

## Cycle 1 — EXECUTION lessons (harness validated; not a finding yet; fixes for cycle 2)
- **Attention-MIL harness works** (torch attention-MIL over per-window embeddings trains on CPU; site-probe
  confound check implemented). Per-window frozen embedding cache builds ~3 s/patient, checkpointed/resumable.
- **BUG: cache samples all-positives THEN all-negatives** → any PARTIAL cache is class-degenerate (at 177
  cached, abnormal was 177/177 positive). FIX: interleave pos/neg (and sites) so a partial cache is always
  balanced and cross-site-ready early.
- **Power: cognitive-syndrome is only ~9% of the abnormal-balanced sample** (16/177) → underpowered for the
  cognitive-PRIMARY flagship. FIX: sample the cache balanced ON THE OUTCOME (cognitive+/- and, separately,
  died/survived), not on abnormal/normal. Embeddings already cached are still reusable as the negative pool.
- **Cross-site needs BOTH sites cached**; the cache does S0001 fully before I0002. FIX: interleave sites or
  run a parallel I0002 cache so the gated cross-site eval can run.
- CPU MIL training (5-fold × 50 epochs × ~150 bags) is minutes-slow but fine overnight; keep the head tiny.
- **Cycle-1 net:** design hostile-reviewed + corrected (cognitive primary + site gate), novelty confirmed
  (white space), substrate + harness built and validated. NO finding claimed (correctly). Cycle 2 =
  outcome-balanced cache of BOTH sites → gated cross-site cognitive/mortality MIL eval → full result gate.

## Cycle 2 — RESULT + hostile-review gate (first complete gated cross-site experiment)
**Experiment:** frozen CBraMod per-window embeddings → attention-MIL, cross-site S0001↔I0002 (abnormal +
cognitive), with the mandated site-probe. n=327 (S0001 239, I0002 88).
**RESULT (fails the site-invariance gate):**
- **SITE-PROBE: pooled embedding → hospital AUC = 0.961** (5-fold). The frozen embeddings encode HOSPITAL
  almost perfectly → severe site/hardware confound. Any cross-site outcome AUC is confounded until corrected.
- Cross-site abnormal MIL: 0.50 / 0.53 (in-sample 0.52 = chance) — degenerate from class imbalance
  (S0001 has 17 normals vs 222 abnormal; can't learn the minority class).
- Cross-site cognitive MIL: 0.62 / 0.58 (in-sample 0.59) — weak + underpowered (I0002 has only 5 cog+).
**Hostile-review gate → VERDICT: no finding; the naive frozen approach FAILS the site gate.** Attack→outcome:
- *Stats/overfit:* even in-sample AUC is ~chance (abnormal) / weak (cognitive) → the frozen-MIL over
  amplitude-dominated embeddings has little usable outcome signal here; imbalance makes abnormal degenerate.
- *Causal/confound:* site-probe 0.96 IS the confound, quantified — the model can shortcut on hospital.
  Confirms the mean-pool-ceiling + amplitude-domination lessons carry to per-window MIL too.
- *External validity:* cross-site AUCs are both confounded AND near chance → nothing to validate yet.
**Fixes (queued for cycle 3):** (1) fit `analysis/correct_sites.py` Route-A site-correction on the TRAIN
site only; re-run site-probe — REQUIRE post-correction site-AUC ≤ ~0.6 as the published gate before any
outcome model. (2) Fix class balance (cache many more NORMAL EEGs — they're rarer/large-file) and boost
cognitive positives (outcome-balanced sampling). (3) If corrected site-invariant embeddings still give
weak outcome AUC, that is evidence the FROZEN path is insufficient and fine-tuning (GPU) is required — an
honest, publishable methods result either way.

## Cycle 3 — site-correction + re-test + power calibration (attack → outcome; the most important cycle yet)
**Experiment:** fit Route-A ComBat/CORAL on the S0001 reference windows, align I0002 as a new site (no
outcome), re-run the site-probe with BOTH a linear and a nonlinear probe, re-test the outcome MIL, and
run an injected-signal power calibration. n=327 (S0001 239 / I0002 88).
- **KEY LESSON — a linear site-invariance gate gives FALSE assurance.** ComBat and CORAL both drop the
  *linear* logistic site-probe 0.961 → **0.585** (would "pass" a ≤0.6 gate), but a *nonlinear* attention-MIL
  still recovers hospital at **0.964 (ComBat) / 0.991 (CORAL)** from the SAME corrected embeddings. CORAL
  (covariance-matching) makes residual site *more* nonlinearly separable. Mechanism: ComBat/CORAL only
  remove 1st/2nd moments; higher-order/nonlinear site structure survives and a flexible model exploits it.
  **IMPLICATION: the site-invariance gate MUST be nonlinear (attention-MIL / NN probe), not logistic.**
  The measured residual is a LOWER bound (single fit; the only leakage makes sites more similar → deflates
  site-AUC). Novelty: INCREMENTAL — unpublished in EEG-FM (closest: Murchan 2024 pathology, pre 0.96→post
  0.51, never ran a nonlinear probe), but ComBat-only-removes-location/scale is textbook. Red-team verdict:
  reframe as "empirical demonstration + gate recommendation," needs per-fold CIs + ≥3–5 sites to publish
  even as a methods note. Best home = the site-gate methods section of the main study, NOT a headline.
- **LESSON — power-calibrate every null before believing it.** Cognitive-outcome MIL on corrected
  embeddings = 0.466 (25 pos, inside permutation null [0.35,0.59]); in-sample ≈chance too. Injected-signal
  calibration at the real n=25 regime: pipeline recovers 0.30σ→AUC 0.586, 0.60σ→0.842, but 0.15σ→chance.
  So the null **excludes a STRONG frozen cognitive signal but NOT a weak one.** "In-sample ≈ chance" does
  NOT by itself prove "no signal" — it is also consistent with underpower/label-noise/probe-misspecification.
  Always run an injected-signal (or positive-control-outcome) power check before writing any "no signal" or
  "motivates fine-tuning" language. Abnormal-EEG at 90% prevalence (295/327) is uninformative → drop it.
- **LESSON — the frozen mean+std representation is impoverished (positive-control outcome check).** Ran
  age/sex (which EEG is KNOWN to encode: sex ≈0.70–0.85, age strong) through the identical MIL+OOF pipeline:
  sex OOF **0.50** (chance), age OOF **0.55 all / 0.61 S0001-only**. Age is balanced at n=327 → NOT a power
  problem. With the injected-signal calibration proving the harness recovers signal that IS in the
  embeddings (0.6σ→0.84), the conclusion is the **representation** (frozen mean+std pooling of tokens) is
  the bottleneck, not the harness or the label count. **This is the cleanest evidence yet that frozen
  mean-pooling is the wrong representation** (corroborates the mean-pool-ceiling lesson at MIL level).
- **KEY FORK (top of cycle-4 queue, CPU-runnable):** the culprit may be the **mean+std pooling** (collapsing
  the 19×30 per-window tokens to 400-d) rather than the frozen ENCODER. Test with a **full-token
  attention-MIL** (no mean+std collapse) + re-run the age positive control. age≳0.75 → pooling was the
  bug, a positive finding may be reachable ON CPU (redo outcomes with full tokens). age still ≈0.6 → the
  frozen encoder is insufficient → GPU fine-tuning. This cleanly separates "my pooling choice" from "frozen
  encoder limit" — do it before spending on GPU.
- **NET:** the frozen **mean+std** + CPU path cannot deliver a positive cross-site clinical finding at this
  n; the site confound is nonlinear (survives linear harmonization) and the representation barely encodes
  even age. Full writeup: `docs/CYCLE3_SITE_INVARIANCE.md`.
- **Cycle-4 pilot (full-token, channel-resolved): did NOT rescue the representation.** Re-embedded 80
  S0001 EDFs keeping per-channel tokens (pool time only, 228 tokens/bag); age>median OOF AUC = **0.443** vs
  mean+std 0.610 — no improvement. CAVEATS: different subset, NWIN=12, and per-token standardization across
  228 heterogeneous channel tokens likely adds noise → treat as suggestive, not a clean verdict. **Lesson:
  richer frozen pooling is not a free CPU win**; the weight of evidence now points at the frozen ENCODER
  itself (→ GPU fine-tuning) rather than my pooling choice. Clean decider = a MATCHED full-token comparison
  (same patients/NWIN, better token norm) — but the ceiling looks like fine-tuning, not pooling.

## Open opportunity (the current best shot)
- **No EEG foundation model has been applied to clinical/neuro outcome prediction with external validation
  anywhere (as of 2026)** — DELPHI-EEG is single-center. HEEDB (multi-site EEG + ICD10/OMOP outcomes +
  DateOfDeath) enables the first cross-site-validated EEG-foundation-model outcome study. Pipeline
  validated, preprocessing solved (µV). Now approachable on CPU overnight via the frozen-embedding + MIL-
  head path (see process lesson above); encoder fine-tuning deferred to a future GPU env.
