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
- **Cycle-4 DECIDER (matched full-token vs mean+std): the frozen ENCODER is the ceiling, not the pooling.**
  Clean apples-to-apples test — SAME patients, SAME windows (NWIN=24), SAME folds; one embed pass emits BOTH
  mean+std (24×400) and channel-resolved full-token (456×200). Age>median OOF AUC at n=98: **mean+std 0.401
  vs full-token 0.476 — both ≈chance.** Richer pooling gives NO meaningful rescue. The frozen CBraMod
  representation does not reliably encode even age (an easy, strong EEG target) under any pooling tested.
  (An earlier mean+std 0.61 at n=239 was subset-dependent; on a clean random subset it collapses to ~chance
  → the frozen age signal is fragile.) **DEFINITIVE LESSON: the CPU/frozen path is exhausted for a positive
  clinical finding — encoder FINE-TUNING (GPU) is the required lever, not a better CPU pooling.** Stop
  spending CPU on frozen-representation tricks; the next real move needs a GPU.

## Cycle 5 — CPU pivot to VitalDB (anesthesia), induction MAP-recovery-τ → postop AKI: clean NULL
- **Novelty pre-screen EARNS its keep — it reframed the idea before compute.** Original "arterial
  wave-reflection recovery kinetics → AKI" was killed by the haiku+PubMed screen for TWO reasons a reviewer
  would hit on sight: (1) named-index proximity (augmentation index, O'Rourke); (2) **pressure-only wave
  separation is discredited** (Mynard 2012, *J Hypertens* — reservoir-wave paradigm "introduces error"),
  and VitalDB has no aortic flow. LESSON: for any waveform-morphology marker, check whether the physiologic
  decomposition needs a signal you don't have — pressure-only ≠ wave separation. But the screen also
  CONFIRMED live white space beneath it (higher-MAP-target RCTs are null → field wants a dynamic
  reserve/endotype dimension beyond TWA-MAP), so the fix was to keep the target and swap the marker to a
  pressure-only, non-named one (MAP recovery-τ after induction).
- **Powered NULL (n=1,255, 149 AKI events):** baseline risk (age/sex/ASA/preop-Cr) OOF AUC 0.770; +standard
  intraop hemodynamics 0.806; **+recovery-τ → 0.801 (Δ −0.005)**; τ adjusted coef +0.043 CI [−0.156,+0.187]
  (spans 0). The "slow hemodynamic recovery = vasoregulatory reserve → AKI" hypothesis is NOT supported in
  noncardiac surgery. Did NOT fish for a τ definition that works (garden-of-forking-paths) — one
  pre-specified marker, powered, null. Even TWA-MAP itself is weak here (consistent with the null RCTs).
- **PROCESS WIN (repeat of the Cycle-3 lesson):** the n=162/17-event pilot looked null (τ AUC 0.375) but
  was underpowered; scaling to 149 events (cheap, threaded track fetch) was needed to make the null
  trustworthy. Always power a null before believing it. **Reusable asset:** VitalDB AKI cohort (2,579 cases,
  ~305 events) + cheap 2 s numeric-hemodynamics pipeline (threaded VitalDB `/labs`+track fetch), for future
  markers/outcomes with no re-fetch. Detail: `docs/VITALDB_PIVOT_IDEA2.md`.

## Cycle 6 (candidate vetting) — a structural lesson + a feasibility gate that correctly killed the top pick
- **STRUCTURAL CEILING for observational ICU treatment-decision designs (~OR 1.35).** Our two prior
  properly-adjusted treatment-decision studies — vasopressor dose→mortality and 3-way liberation-order —
  converged on the **IDENTICAL OR ≈ 1.35 / E-value ≈ 1.83** after honest severity adjustment. That is
  almost certainly not coincidence: once severity-at-decision is adjusted, residual confounding-by-indication
  in EHR data leaves a stereotyped small effect. IMPLICATION: any new treatment-decision question (e.g.,
  de-resuscitation, de-escalation) should be expected to top out near there — prefer **MECHANISM** questions
  (exposure not chosen by a clinician reacting to severity) or **quasi-natural-experiments** (an exogenous
  timer like lab turnaround) over treatment-decision designs.
- **MIMIC-IV has NO routine ward vitals** (a feasibility fact worth remembering): `chartevents` is
  ICU-module only; pre-ICU vitals exist only in the separate MIMIC-IV-**ED** module. Any "ward deterioration
  / early-warning / pre-ICU vitals" question is not constructable in MIMIC-IV proper — this killed the
  otherwise-best Cycle-6 candidate ("vitals-first vs labs-first" mechanism) at the make-or-break gate before
  any compute. The gate did its job. Candidate slate + options: `docs/NEXT_CANDIDATES_MIMIC_EICU.md`.

## Cycle 6 (Candidate 3 build) — a clever natural experiment can still die on a WEAK FIRST STAGE
- Built the culture-turnaround natural experiment in MIMIC-IV (all streamed, disk-sparing): index-culture
  instrument for 201k admissions × broad-spectrum antibiotic courses × mortality. Pipeline validated
  end-to-end (n=13,704 empiric cohort; 961 deaths).
- **KEY LESSON — always test the FIRST STAGE (instrument relevance) before believing the design.** The
  exogenous timer (culture turnaround, storetime−charttime) only WEAKLY drives the exposure
  (corr with broad-spectrum duration = **+0.093**). Clinicians de-escalate on clinical grounds, not gated on
  the exact result-availability time → a weak instrument that caps the whole design's causal power. The
  reduced form (turnaround → mortality) is EXACTLY null (AUC 0.500). A quasi-natural-experiment is only as
  strong as its first stage; a clever exogenous-timer idea can still be weakly-instrumented in practice.
  This is the natural-experiment analog of the "power the null" lesson — power/validate the INSTRUMENT first.
- **Process win:** disk-sparing throughout (streamed 3.99M microbiology + millions of prescription rows via
  `wget --netrc | python`, never storing raw tables; a checkpointing reducer survived a flaky proxy). And
  re-confirmed the **heredoc bug** (a `cat <<EOF` script silently didn't update — always use the Write tool).
- Verdict leaning: interesting design, weak instrument → re-rank (mortality null as expected; ecological
  outcomes C.diff/MDRO remain the only shot but would be a fragile IV at +0.09 relevance).

## Cycle 7 — fast eICU cross-hospital screens (169k stays, 207 hospitals): 3 more nulls + a META-pattern
- Tested on cached eICU apacheApsVar×patient (by-hospital OOF, baseline physiology+age AUC 0.790): H1
  relative bradycardia (HR~temp residual) Δ+0.0000; H2 derangement dispersion Δ+0.0052 (0.83-collinear with
  total severity → trivial); H3 race-miscalibration NULL (O/E 0.93–1.05 all groups, +ethnicity Δ−0.0003).
  Incidental: the physiology→mortality model is robust across 207 hospitals AND well-calibrated across race.
- **META-LESSON (dominant after 7 cycles):** on well-powered, well-measured ICU/anesthesia tabular data,
  (a) novel single markers vs strong baselines → incremental nulls; (b) treatment-decision designs → OR≈1.35
  confounding ceiling; (c) natural experiments → weak first stage; (d) equity-miscalibration → well-calibrated
  null. The honest gate keeps (correctly) refusing a winner. **Stop firing marker-vs-baseline tests** — a
  genuine ultra-high-impact winner needs a different lever: the GPU-gated EEG-FM flagship (evidence-backed as
  the real lever), a prospective/interventional element, or a fundamentally new data asset. Detail:
  `docs/CYCLE7_EICU_SCREENS.md`.

## Cycle 8 — RDD (user-chosen): design sound, first target blocked on TREATMENT CAPTURE (validate first stage!)
- Chose regression-discontinuity (sharp clinical threshold = quasi-randomization) as the structurally-strong
  causal lever. First target: glucose → insulin-INFUSION (eICU). Built a disk-sparing single-pass streaming
  first-stage (bin-aggregated P(insulin within 3h) by glucose, 563k decision-points).
- **RESULT: P(insulin infusion) ≈ 0 across ALL glucose bins → first stage FAILED, but from CAPTURE not
  absence.** eICU insulin *infusions* are in only 7% of stays (`infusionDrug` incomplete; most ICU
  hyperglycemia is subcutaneous insulin, not in this table) and drip starts are often early (DKA) so few
  glucose values precede them. **LESSON: for an RDD, the make-or-break is the FIRST STAGE (does treatment
  actually jump at the threshold) AND the treatment must be DENSELY/RELIABLY captured — check capture before
  building.** A structurally-sound design still dies if the treatment variable is sparse/mistimed in the data.
- **Infra lesson:** eICU `lab` (~40M rows / ~2 GB) through the agent proxy is slow + drops; repeated full
  streams are impractical. For any full-`lab` analysis, do a ONE-TIME compact filtered extract (only the
  needed labnames) instead of re-streaming. Checkpointing reducers are mandatory for flaky-proxy streams.
- **Path forward (RDD still live):** use a densely-captured threshold-treatment — MIMIC-IV `inputevents`
  charts insulin + electrolyte repletion (K/Mg/phosphate) with times; **electrolyte repletion at protocol
  thresholds has ~no outcome evidence → the most NOVEL RDD target.** Transfusion@Hb7 is the sharpest but
  answer-known (methods-validation only). Detail: `docs/CYCLE8_RDD.md`.

## Cycle 8 (cont.) — RDD of electrolyte repletion: the FIRST GENUINE LEAD (valid design + novel null)
- Pivoted the RDD to a densely-captured, evidence-free practice: Mg repletion at ~2.0, K at ~3.5 (MIMIC-IV;
  running variable + mortality fully CACHED, treatment from a streamed compact inputevents repletion extract).
- **First stage VALID:** P(repletion≤6h) jumps at the threshold (Mg sharp ~4× at 2.0; K graded below 3.5).
  This is the first valid RDD first stage of the whole search — the key was a DENSELY-captured treatment.
- **Reduced form (cached, treatment-independent) = well-powered mortality NULL:** Mg RD −0.0006 (n=176k),
  K RD −0.0005 (n=191k); binned mortality smooth through both cutoffs. → reflexive electrolyte repletion has
  no detectable causal mortality effect = a de-implementation / low-value-care signal on a ubiquitous practice.
- **LESSON — the reduced form of an RDD needs only running-variable + outcome (both cached here), NOT the
  treatment.** So the outcome discontinuity is testable independent of (and faster than) the first-stage stream.
- **Caveats to resolve before it's a WINNER (logged in CYCLE8_RDD_ELECTROLYTE_LEAD.md):** (1) digit heaping →
  discrete-RDD inference (Kolesár–Rothe) + manipulation test; (2) mortality is the SECONDARY endpoint —
  arrhythmia is the mechanistic one (needs chartevents, not cached); (3) decision-point/running-variable
  sensitivity; (4) eICU external validation. This is the best lead so far — valid design + novel,
  externally-validatable null — worth hardening rather than another fresh cycle.

## Cycle 8 (cont.) — COMPREHENSIVE outcome-wide RDD: repletion is inert across ALL known outcomes (the WINNER)
- Tested every known consequence of hypo-Mg/hypo-K (17 ICD complications + mortality + LOS = 38 RDD tests,
  BH-FDR): atrial fib, ventricular arrhythmia, cardiac arrest, brady/heart-block, torsades/long-QT, seizure,
  delirium, ileus, rhabdo, muscle weakness, resp failure, AKI, hypocalcemia, metab alkalosis, MI, shock.
- **METHODS CATCH (crucial):** a naive difference-of-means-in-window RD gave a dozen "p≈0" hits — all were
  the smooth CONFOUNDED electrolyte-outcome slopes, NOT jumps. Proper **local-linear RD** (line each side,
  gap at cutoff; sandwich SE) removes the slope → **0 of 38 survive FDR.** LESSON: for RDD, difference-of-means
  over any nonzero bandwidth conflates slope with discontinuity; ALWAYS use local-linear (or the estimate is
  just the confounded association). This single fix flipped "12 findings" → "clean comprehensive null."
- **FINDING (the session's winner candidate):** threshold-triggered Mg/K repletion has NO causal effect on
  mortality, LOS, or ANY known complication (n≈128k Mg/54k K near-cutoff, MIMIC-IV). Comprehensiveness
  strengthens it — if repletion did anything, ≥1 of 17 mechanistic outcomes should have moved; none did.
  Novel (no prior RDD of repletion across its outcomes), high-impact de-implementation, rigorous
  (local-linear + FDR + acuity-robust + multi-threshold smooth). Only nominal signal = Mg→delirium (z−3.0,
  fails FDR) → hypothesis for a timed-outcome follow-up. Detail: `docs/CYCLE8_RDD_ELECTROLYTE_LEAD.md`.
- Remaining hardening (loop): eICU replication (proxy-bottlenecked stream); discrete-RDD inference for the
  heaped running variable; time-resolved delirium/new-AF endpoints (chartevents); density/covariate checks.

## Deconfounding methods — the assay-noise instrument (the /goal deep-dive)
- **The universal obstacle, restated:** reflexive lab-triggered treatment (electrolyte/PPI/transfusion/insulin)
  is a near-deterministic function of a time-varying severity signal that also drives the outcome. Proven that
  RDD (no discontinuity), provider-IV (exclusion fails), within-patient FE (sicker episode), IPTW (RR 4.17)
  all break on it → motivates a design that uses EXOGENOUS variation unrelated to the individual's prognosis.
- **The idea — assay-noise IV ("lab lottery"):** measured lab = true + analytic/biologic noise; conditional on
  the TRUE value, which side of a flag the noisy value lands on is as-good-as-random → an exogenous instrument.
  Grounded in CLIA analytic imprecision (auditable, severity-independent). Applies to every lab-flag treatment.
- **CORE IDEA IS PRIOR ART** (do not claim as novel): noise-induced randomization at a threshold — Eckles,
  Ignatiadis, Wager, Wu (*Biometrika* 2025); Pei–Shen RDD-with-measurement-error (2017); Barreca et al.
  birthweight-heaping-at-1500g is the closest clinical cousin (and solved the same leaky-control trap).
- **RED-TEAM CLAIM OVERTURNED BY SIMULATION (the important one — validate fixes, not just findings):** the
  referee argued control `T̂=(M1+M2)/2` shares noise with `Z=1(M2<flag)` → biased toward false HARM, and
  prescribed dropping M2 (control on M1 only). A known-truth Monte Carlo (`docs/ASSAY_NOISE_IV_SIMULATION.md`,
  `docs/sim_assay_noise_iv.py`) **refuted it**: for EQUAL-variance noise, conditional on the midpoint the instrument
  driver `∝(ε2−ε1)` is ORTHOGONAL to the severity driver `∝(ε1+ε2)` (Cov = Var(ε2)−Var(ε1) = 0), so the
  midpoint control is EXACTLY unbiased (sim balance on true severity = 0.0000, LATE recovers truth; robust to
  drift) and the original age-balance (+0.27yr≈0) was VALID. The prescribed "M1-only" fix is the BIASED one
  (sim balance −0.12). **Mechanism of the real vulnerability:** midpoint bias `∝ Var(ε2)−Var(ε1)` → breaks only
  under ASYMMETRIC noise (draws at different times/analyzers); robust general control = LOCAL many-draw
  leave-one-out proxy (bias→0 as draws accumulate). LESSON: an over-claimed refutation is as damaging as an
  over-claimed finding — simulate the FIX against a known truth before adopting it. The first Mg numbers are
  NOT void on shared-noise grounds; they still must pass the OTHER threats below.
- **Naive repeated-measurement pooling gives a DEGENERATE ≈0 first stage** because (a) post-treatment draws
  aren't fresh decisions (must be absorbing-censored) and (b) eligibility defined on the NOISY value conditions
  on the instrument. FIX = the **renewal design**: eligible node = not-yet-treated ∧ near-flag on the
  NOISE-FREE proxy `T̂_{-t}`; stack across nodes; cluster SE on patient. This recovers ~√(mean draws/patient)
  power the single-draw design throws away and is the genuinely NOVEL piece (serially-correlated-noise-
  randomized repeated decisions with an absorbing treatment + terminal outcome; leave-one-out control for a
  latent serially-correlated state). Full write-up: `docs/ASSAY_NOISE_IV_METHODOLOGY.md`.
- **σ from far-apart draw-pairs OVER-estimates pure assay noise** (conflates analytic error with true biologic
  drift) → re-estimate by inter-draw interval (drift signature if σ grows with Δt) and severity stratum.
- **Bulletproof = falsification battery, not a number:** McCrary/CJM density test at the round threshold
  (heaping → donut hole) FIRST; bundle-balance (flag may trigger telemetry/co-repletion/monitoring, not just
  the treatment → exclusion fails); weak-IV-robust inference (Anderson–Rubin, lead with reduced-form ITT, not
  delta-method LATE); competing-risks (in-hospital mortality is LOS-dependent → 30/90-day, Fine–Gray).
- **Packaging = convergent partial identification:** combine a harm-biased design (IPTW/provider-IV) + a
  benefit-biased design (treatment withheld from the sickest / healthy-user elective strata) to BRACKET the
  truth, with the corrected assay-noise reduced form as the ~unbiased anchor → Manski-style reviewer-proof bounds.

## Deconfounding methods — prior-art & power (gap-analysis cycle)
- **PRIOR ART IN OUR OWN DATABASE (novelty-check that could have sunk us):** Bosch et al. *Ann Am Thorac Soc*
  2022;19(7):1177-1184 already ran a fuzzy RDD at Hb 7.0 g/dL **in MIMIC-IV** (co-author Bor), justified by
  "measurement noise pseudorandomizes" — transfusion mostly NULL on organ dysfunction. So "assay noise at a
  clinical threshold" is NOT novel. Our defensible novelty narrows to: formal estimable noise model (instrument
  built FROM assay CV / serial-pair variance, vs their prose justification) + renewal/repeated-decision
  extension + application to Mg/K where NO RCT exists. LESSON: always run a database-specific novelty scan before
  claiming a design is new; the same clever idea is often already in the same dataset.
- **RCT-ANCHOR for method validation = Hb transfusion (graded truth):** restrictive non-inferior in general ICU
  (TRICC/TRISS/FOCUS/Cochrane RR 0.99/AABB) but CONTESTED in cardiac-surgery (TITRe2 mortality HR 1.64 P=0.045)
  and acute-MI (MINT P=0.07 favoring liberal). Dual-stratum recovery (clean null + contested signal) is a
  STRONGER validation than recovering one null. Glucose is a POOR anchor (Leuven→NICE-SUGAR reversal = no stable
  truth) despite better noise magnitude → reserve as a novel-white-space 2nd paper.
- **ASSAY-NOISE VIABILITY by treatment (noise SD as % of threshold gap):** Mg ~6.7% (good); glucose 10-35% via
  POC-vs-central discordance (best); Hb only 1-2% (weak noise-IV — but Bosch showed the RDD-proximity first stage
  at Hb 7 is >20pp, i.e. plenty of near-threshold variation; the noise-specific slice is the weak part).
- **POWER TRUTH (closes 'is it decisive?'):** per-patient LATE for mortality is NOT identifiable in practice
  (MDE 5-12pp at 3-6pp first stage). The flag-ITT (reduced form) IS well-powered (sub-pp MDE) and is the
  de-implementation policy contrast. BUT a bare null ITT is a Type-II TRAP with a weak first stage (consistent
  with 'inert' OR 'diluted-and-unseen') → ALWAYS report ITT + implied-LATE interval (ITT/FS, Anderson-Rubin CI).
  The ITT does NOT escape the exclusion restriction — it inherits it (correct the earlier over-claim).
  Power code: `docs/power_mde_assay_noise_iv.py`. Full ledger: `docs/DECONFOUNDING_GAP_ANALYSIS.md`.

## The 10-trial portfolio & the "universal solvent" structure (key strategic insight)
- **Confounding-by-indication has DIFFERENT trigger structures → needs DIFFERENT instruments; no single solvent.**
  The 10 de-implementation trials split: LAB-FLAG-triggered (Mg/K, RBC, bicarb, partly albumin) → assay-noise IV;
  SYMPTOM/GESTALT-triggered (benzo, opioid, antipsychotic, steroid, PPI-vent-arm) → provider-preference IV;
  RISK-SCORE-triggered (VTE-ppx) → score-RDD. Match the instrument to how the treatment is actually decided.
- **THE creative unlock — three NEW broadly-applicable instruments (push coverage 40%→near-universal):**
  (A) **Contraindication-GATE assay-noise IV:** most gestalt treatments have a MEASURED gate that WITHHOLDS them
  (antipsychotic⊣QTc>500; SUP/anticoag⊣platelet<50k/INR>1.5; steroid via eosinophils; benzo via CIWA) — apply the
  noise-IV to the gate, not the indication. Even cleaner exclusion (crossing QTc 500 only withholds the drug).
  (B) **Nurse-PRN-administration preference IV:** for PRN drugs the ORDER is confounded but the nurse's
  administration-given-order is far more exogenous (nurse practice/workload) → nurse-preference IV on emar events.
  (C) **Attending-rotation time-RDD:** scheduled handoff changes prescribing for the SAME patient at an
  as-if-random time → exogenous within-patient shock that fixes naive within-patient FE's sicker-episode flaw.
- **Near-universal solvent = matched toolkit {indication-flag noise-IV ∪ gate noise-IV(A) ∪ nurse-PRN-IV(B) ∪
  attending-rotation-RDD(C) ∪ prescriber-preference-IV-within-fixed-indication} + negative-control calibration +
  triangulation bounds + RCT-anchored validation.** The RCT-anchoring answers the deepest attack ("CBI is
  observationally unsolvable → that's why we RCT"): calibrate on the settled cases (transfusion/glucose/
  antipsychotic/COPD-steroid), only then extrapolate to the vacuums. Docs: PORTFOLIO_10_TRIALS.md, BESPOKE_METHODS_6_TRIALS.md.
- **Reviewer-attack through-lines (all trials):** ascertainment bias in outcomes (sicker→more testing: C.diff,
  pneumonia, VTE, bleed) → negative-control calibration; reverse causation (delirium→benzo) → landmark/lag;
  indication heterogeneity (steroids) → FIX one indication; provider-IV exclusion (habit~intensity) → within-service
  + near-far matching. MIMIC structural limits: PPI/benzo/opioid/steroid are in `prescriptions`/`emar` (not ICU
  inputevents); QTc in chartevents (ICU-only); calendar obfuscated (shortage/guideline DiD infeasible).

## Simulation result: NEGATIVE CONTROLS ARE MANDATORY for preference instruments (balance is not enough)
- Known-truth sim (`docs/sim_instruments.py`, `docs/SIM_INSTRUMENTS_RESULTS.md`): for provider-preference IV,
  when provider PREFERENCE (the instrument) correlates with provider CARE-QUALITY (which affects outcomes = an
  exclusion violation), the LATE is badly biased (+0.11 vs truth 0) BUT patient **covariate balance stays clean**
  (quality is provider-level, orthogonal to patient severity). The **negative-control-OUTCOME coefficient tracks
  the bias almost exactly** (+0.111) → empirical-null calibration (`negcontrol.py`) removes it. LESSON: for any
  preference-type instrument (provider-IV, attending-RDD, nurse-PRN), covariate balance is necessary but NOT
  sufficient; NC-outcome calibration is a REQUIRED gate. A preference-IV paper reporting only balance is not
  bulletproof. (Also validated: nurse-PRN estimator recovers truth −0.027 vs −0.030; aggregation is sound.)

## Open opportunity (the current best shot)
- **No EEG foundation model has been applied to clinical/neuro outcome prediction with external validation
  anywhere (as of 2026)** — DELPHI-EEG is single-center. HEEDB (multi-site EEG + ICD10/OMOP outcomes +
  DateOfDeath) enables the first cross-site-validated EEG-foundation-model outcome study. Pipeline
  validated, preprocessing solved (µV). Now approachable on CPU overnight via the frozen-embedding + MIL-
  head path (see process lesson above); encoder fine-tuning deferred to a future GPU env.

## Assay-noise IV, ALL benchmark trials emulated (2026-07): the toolkit is self-diagnosing (each failure has a distinct, gate-caught mechanism)
Emulated every lab/gate-triggered benchmark trial as faithfully as possible (exact protocols, all factors; see
`docs/TRIAL_EMULATION_MASTER.md` + per-trial `REAL_RESULTS_*`). Result — the cross-method assay-noise IV is
validly IDENTIFIED for exactly ONE analyte, and the gates correctly reject it everywhere else, each for a
different diagnosable reason:
- **Hb (TRICC/TRISS)** ✅ RECOVERED THE RCT NULL. Cross-method CBC-Hb vs blood-gas-Hb = pure analytic discordance
  (shared measurand co-ox/impedance, both measure intact Hb). Faithful all-factors emulation (ICU, Hb≤9 w/in 72h,
  exclude bleeding/chronic-anemia/cardiac/pregnancy, 30-/90-day) → flag-ITT≈0 in every powered stratum. The
  earlier "+0.032 harm" was temporal drift (bleeding) + wrong endpoint + included bleeders, not method failure.
- **Glucose (NICE-SUGAR)**: two NEW lessons. (1) **Build the instrument on the measurement the clinician ACTS ON**
  — chem-glucose flag → correctly-signed strong first stage (F 15–26); blood-gas-glucose flag → strong-but-
  WRONG-signed (insulin dosed off chem/POC, not ABG). First-stage SIGN is a required gate the F-stat misses.
  (2) **Estimand boundary**: a single flag ≠ NICE-SUGAR's target-range contrast → flag-ITT≈0 is the shared
  correctional-insulin decision, not the trial; needs a dose-intensity IV.
- **Potassium**: acted-upon rule replicates (chem-flag F 59–64), but **NC FIRES** (K-flag predicts RBC transfusion,
  which K can't trigger) — mechanism = **hemolysis** reads falsely-high K and perturbs the two assays non-randomly.
  Age balance PASSED while NC failed → the canonical "balance-passes-while-exclusion-violated" case. Retired.
- **NC audit across Hb/glucose/K** (`REAL_RESULTS_NC_AUDIT.md`): ALL flags carry a small residual-acuity leakage
  (+0.016..+0.029), significant where n is large → **never test flag-ITT against 0; NC empirical-null calibration
  is mandatory**. Hb cleanest but its NC is underpowered (don't over-claim it's provably clean).
- **Platelet (TOPPS)**: no second same-time method exists in MIMIC (only impedance 51265). Temporal fallback fails:
  short-interval (<2h) sigma near the <10 flag is LARGER than long-interval (transfusions between draws + marrow
  kinetics) → drift-contaminated. Retired. = the "single-method" failure class.
- **Albumin (ALBIOS) + Bicarbonate (BICAR-ICU)**: single-method temporal IV — drift diagnostic fails (short-gap
  sigma NOT << long-gap; short is selected for instability) AND NC fires. Bicarbonate AKI subgroup also NC-fails.
  Retired. Albumin additionally weak first stage.
- **MIND-USA (antipsychotic)**: nurse-preference instrument STRUCTURALLY fails (F<1) — emar provider field is
  charted conditional-on-administration (assignable⇒98.9% exposed) → LOO first stage mechanically dead. Honest
  data-limitation, not a coding bug.
MECHANISM/META-LESSON: cross-method assay-noise discordance is clean ONLY when the two assays share the same
physical measurand AND failure modes (Hb). It fails via: single-method (platelet, albumin, bicarb temporal),
non-analytic artifact correlated with acuity (potassium=hemolysis), wrong flagged side (glucose/K=fixable),
estimand mismatch (glucose target-range), or charting-conditional exposure (MIND-USA). The publication-grade
claim is NOT "assay-noise IV works" — it's "a SELF-DIAGNOSING assay-noise toolkit whose gates (first-stage sign,
drift diagnostic, NC empirical-null) recover TRICC/TRISS on Hb and correctly REJECT the instrument on 5 other
decisions, each for a distinct mechanistic reason." Honesty about scope IS the contribution.

## Sodium method-discordance = the ONE positive Sjoding-template win (measurement bias, not causal IV)
The same paired-draw machinery that FAILED as a causal instrument (power wall) SUCCEEDS as a measurement-bias
discovery: chemistry Na (indirect ISE, protein-sensitive, the acted-on value) vs blood-gas Na (direct ISE,
reference). The chem−bloodgas gap is **racially differential** in MIMIC (BLACK−WHITE −1.18 mEq/L, z=−12.6;
robust to ≤10-min pairing −1.30). This dodges every wall that capped the causal analyses because it needs NO
first stage — it is a measurement-agreement + association design (the Sjoding pulse-ox NEJM-2020 template).
- **Mechanism NAILED by graded dose-response, cross-nationally.** gap ~ total protein slope −0.90 (MIMIC, z=−6.4)
  and **−0.843 (SICdb/Austria, z=−28.6, monotone across protein quartiles +2.02→−0.06)**. Two continents, two
  analyzer fleets, near-identical slope → indirect-ISE pseudohyponatremia is physics, not a MIMIC artifact. Total
  protein & globulin gap are higher in Black patients (6.42 vs 5.83; 3.04 vs 2.60) → the mediated racial path.
- **Confounder-robust:** survives full adjustment (age/true-Na/renal/glucose/lipids/albumin) at −0.80 (z=−8.1);
  total protein is the MEDIATOR (adjusting for it attenuates, as a mechanism should — not a confounder).
- **Not a per-unit analyzer artifact:** within-care-unit FE keeps BLACK at −0.62 (z=−6.9), consistent 7/9 units.
- **A–V confound excluded by SPECIFICITY:** glucose has a larger A–V gradient, differs by race, yet ZERO racial
  bias (z=+0.8); bicarb null. Effect is specific to analytes where the indirect-ISE protein artifact operates.
- **Consequence:** at matched true-normal Na, adjusted false-hyponatremia-label OR 1.68 (z=+3.0); hypertonic-saline
  overtreatment 2.9× crude but underpowered (21 events) → report misclassification as the demonstrable harm.
- **External-validity ceiling on the RACE axis:** race + dual-method sodium co-occur only in MIMIC among public
  ICU datasets. eICU has race but records **only chemistry Na** (90k rows all labtypeid=1, no blood-gas Na) →
  cannot replicate. SICdb has both methods + abundant total protein but **no race** (single-center Austria) →
  replicates the MECHANISM only. Sex axis did NOT replicate (opposite direction MIMIC vs SICdb) — not claimed.
META: the paired-measurement toolkit's publication-grade output is not a causal effect but a MEASUREMENT-BIAS
finding — racial pseudohyponatremia from routine indirect-ISE sodium, mechanism cross-nationally confirmed. The
causal-IV program's negative results (power wall) and this positive measurement-bias result are the same data
viewed two ways; the measurement-bias framing is what clears the impact bar.

## Sodium finding survived 4 rounds of hostile review — and a review CAUGHT a stale eICU overclaim
The racial indirect-ISE sodium bias was stress-tested through 4 adversarial rounds (2 with independent code
re-execution by hostile referees). Every core MIMIC/SICdb number reproduced digit-for-digit; all FATAL-flagged
attacks (asserted-reference, SICdb-inversion, Hgb-specificity, disease-confounding, glucose/BUN-arbiter, selection)
were answered with data. KEY CORRECTION a referee caught: the eICU osmolality-fingerprint restream had COMPLETED
(9.8M rows) while I worked elsewhere; I'd left the section as "in progress (n=457)" with a prediction "~z-1.3 even
at full n". The full file (n=5,440) FALSIFIED it: the eICU racial differential is sign-unstable (raw +0.26; adjusted
+0.93 WRONG direction; hospital-FE -0.22 ns) -> a between-hospital-analyzer confound, NOT a replication. Only the
protein MECHANISM replicates in eICU (dose-response -0.39/g/dL, z=-4.1). LESSON: (1) always re-run analyses on
completed background streams before writing conclusions - a stale partial + a confident prediction is exactly what a
reviewer with public-data access reproduces in minutes; (2) a racial measurement-bias test needs a SINGLE-analyzer
setting - a 208-hospital osm reconstruction is confounded by site calibration x racial composition, which is WHY the
clean signal lives in single-center MIMIC and cannot be externally replicated in public data (structural ceiling).
Honest tier after review: methods/equity research letter, NOT NEJM/JAMA original (single-center race, misclassification-
not-outcome harm, analyzer-specific magnitude). The mechanism (protein-driven pseudohyponatremia) is the durable,
cross-nationally-validated part.

## Cycle 9 — critical-care/anesthesia measurement-bias batch (5 ideas, MIMIC-IV in hand)
- **DATA-QUALITY LESSON (SaO2/occult-hypoxemia):** MIMIC-IV labevents itemid **50817 "Oxygen Saturation" (Blood Gas) mixes ARTERIAL and VENOUS specimens** — the cached `lab_sao2.csv` has p25=70, p10=57 (a clear SvO2 ~60-75% cluster), so 36% "SaO2<88" is spurious venous contamination. Do NOT compute occult-hypoxemia magnitude from 50817. Clean arterial O2-sat is **chartevents itemid 220227 (Arterial O2 Saturation)** — re-extract before quantifying. The RACIAL DIRECTION still replicates through the noise (occult hypoxemia among SpO2 92-96: Black 51.3% vs White 41.8%, adj OR 1.47, z=+3.5 — consistent with Sjoding NEJM 2020), but magnitude + harm need the clean source.
- **DESIGN LESSON (acuity confounding of "occult vs overt"):** contrasting occult (monitor reassuring, truth bad) vs overt (both bad) on mortality is fatally acuity-confounded — overt = actively decompensating, so occult looks spuriously PROTECTIVE (occult-hypoxemia mortality OR 0.30 vs overt, z=-11.0, reversed). The harm must be tested holding the TRUE value fixed (treatment-escalation/recognition at matched truth), not occult-vs-overt outcomes. This warning was propagated to all 4 sibling analyses (cuff/art MAP, MAP threshold, creatinine-AKI, glucose-shock).

## Cycle 9 (red-team) — a METHOD lesson that killed the cuff-MAP finding
- **Never bin/regress a difference (A−B) against one of its own components (B).** The cuff-MAP
  "finding" binned discordance (cuff−art) by arterial MAP and reported +14.42 mmHg over-read at
  MAP<55 with corr −0.645. Both are largely **regression-to-the-mean artifacts**: art appears with
  a minus sign in the outcome, so low-art bins mechanically show positive discordance. Redone on the
  **Bland-Altman x-axis mean(A,B)**: corr −0.645→−0.295, low-band bias +14.42→**+1.49 mmHg** (~10×
  collapse). ALWAYS plot/bias-assess two-method discordance against the mean, not against one method.
  (Protective note for the sodium/calcium work: those regress the *racial differential* in bias — a
  difference-of-differences at matched true value — so RTM cancels across race arms; the race
  coefficient is safe. Only per-true-value slopes would be affected.)
- **Harm signals from "occult vs overt" reverse under a sustained/persistence filter.** Cuff under-
  titration OR 0.822 (z=−4.19) → 1.14 (ns) once the low reading had to persist ≥1 prior reading —
  transient/artifactual extremes drive the naive signal. Add a persistence filter before believing a
  masked-measurement→treatment link.
- **VERDICT: idea 2 (cuff-MAP) demoted to "known device behavior, no novel/causal claim."** Logged;
  do not resurrect without a full-power sustained-hypotension design and a cuff-only (ward) cohort.

## Cycle 9 (red-team) — the creatinine-AKI winner SURVIVES but is REFRAMED + DEMOTED
- **CHECK PRIOR ART *BEFORE* RUNNING, not after.** The creatinine-masked-AKI-by-sex mechanism is
  ALREADY PUBLISHED (Nat Rev Nephrol: absolute-creatinine organ-failure thresholds disadvantage
  low-muscle women/elderly; a Swiss BMJ Public Health POA-AKI cohort states it explicitly). We
  spent a full analysis before discovering it isn't novel. NEW RULE: a 2-minute PubMed novelty
  pre-screen is mandatory before any "discovery" run (the lit-mining doc 07 now front-loads this).
- **"Isolated criterion" ≠ "the guideline."** Full KDIGO 2012 = absolute OR relative; every "masked"
  patient is relative-positive by construction, so full-guideline KDIGO misses NO ONE. Showing the
  *absolute arm alone* fails is only meaningful for **isolated-absolute EHR auto-alerts** (real, since
  point-of-care baseline for the ratio arm is often unavailable). Don't claim a guideline fails when
  only one OR-arm does.
- **Beware TAUTOLOGICAL robustness checks.** "Restrict to baseline ≥0.6 mg/dL" forces sensitivity to
  1.0 for a (ratio≥1.5, abs≥0.3) pair regardless of sex (0.3/0.5=0.6) — so "the effect vanishes on
  restriction" is arithmetic, not evidence. Always ask whether a robustness check is mathematically
  forced before interpreting it.
- **The effect can be real AND confined to a noise zone.** The entire sex disparity lives at baseline
  <0.6 mg/dL, where a 1.5× rise (0.4→0.6) may be assay/physiologic noise; MIMIC has no cystatin C to
  adjudicate true injury. Robust to baseline-def / RTM / draw-count, but this open limitation caps it
  at a methods/quality LETTER, not a flagship.
- **META: our idea-generation is well-calibrated to the literature.** The 4-venue NEJM/JAMA/Nature
  sweep independently surfaced our OWN corrected-Ca flagship, the K+ two-method discordance, the KDIGO
  creatinine idea, AND the cuff-MAP idea the red-team killed — evidence the template is on-target, and
  that the wins/kills track what top journals consider important.

## Cycle 10 — ten-idea batch: what a top-tier-journal mine actually yields (1 win / 10)
- **Most single-analyte measurement biases are ALREADY PUBLISHED.** The mandatory novelty pre-screen flagged
  6/10 (QTc formula, HbA1c-race, albumin-AG, Hb-method, eGFR-race, bilirubin-Jaffe) as known BEFORE any
  overclaim. Wins require a genuinely uncharted subgroup angle (chloride-by-race = 0 PubMed hits) or a
  specificity dissociation (corrected-Ca race-specific-not-sex).
- **"Differential misclassification by subgroup" usually decomposes into KNOWN-DISPARITY + tiny residual.**
  Run an Oaxaca / within-stratum decomposition BEFORE calling it a measurement finding. Idea 7 (Na-glucose):
  84% was the known Black hyperglycemia disparity, only 16% (~1pp) a race-specific residual → demoted.
- **Cohort substrate can REVERSE an effect.** Benign ethnic neutropenia over-labels Black patients in the
  OUTPATIENT setting, but in MIMIC ICU it reverses (acute chemo/sepsis neutropenia dominates the threshold
  and is more prevalent in White admissions). Match the cohort to where the phenomenon lives.
- **Two-method discordance red-team checklist (validated on chloride WIN):** (1) arterial-venous / specimen-
  compartment confound — split by arterial-line presence; (2) independence from the sibling analyte (adjust
  for concurrent Na-discordance — chloride kept ~69%); (3) is the mechanism (protein) actually powered here
  (chloride: n=134, NOT powered → label mechanism a hypothesis); (4) selection to the paired-labs (ICU/ED)
  cohort limits generalizability. Chloride SURVIVED all four → real 4th analyte, tempered claim −0.8 to −1.3.
- **A rigorous NULL is a deliverable:** corrected-Ca-by-sex null is the flagship's best negative control
  (dissociates the race effect from a generic subgroup artifact). Log nulls; they harden the wins.
- **Net cycle-10 addition to the program:** chloride joins Na/Ca as a coordinated, independently-measured 4th
  analyte in the indirect-ISE electrolyte-exclusion family (docs 01/03) — with mechanism still to be confirmed
  on a cohort where total protein is co-drawn with blood gas (MIMIC pairs it in only ~2% of chloride pairs).

## Chloride use-case round — the "where does a measurement bias PROPAGATE" analysis pattern
- **A coordinated multi-analyte bias can CANCEL in derived quantities.** Because indirect-ISE biases Na and
  Cl proportionally (−1.10, −1.20), the anion gap and strong-ion difference (both ≈ Na−Cl) are SELF-PROTECTED
  (B−W AG bias +0.10, z=0.65) while absolute Cl is not. When you find a measurement bias, always map WHERE it
  propagates: derived quantities that subtract co-biased inputs may be immune — a clinically actionable and
  novel result either way. (Temper: the cancellation null was underpowered, CI −0.21..+0.42; needs external rep.)
- **Threshold-crossing "residuals" are often case-mix, not bias.** The AG>16 apparent false-HAGMA push (z=3.09)
  was an artifact of Black patients' higher TRUE anion gap putting more mass near a fixed cutoff — NOT a
  differential bias mechanism. Always stratify by the true value before attributing a pooled threshold gap to bias.
- **Separate the measurement disparity from the clinical-harm claim.** The false-hypochloremia finding is a solid
  measurement-classification disparity (Fisher p=0.0001) but the mortality-marker "over-flags high-risk" framing
  collapsed under partial severity adjustment (OR 2.77→1.28) and there's no CDS tool in use — so it's a
  documented misclassification, not proven point-of-care harm. Claim the measurement layer; don't overreach to harm.

## Fluid-responsiveness scoping (pre-run) — the label problem dictates the substrate
- **MIMIC/eICU LACK the stroke-volume ground truth.** No continuous SV/CO for the general cohort; arterial MAP is
  ~1/hour with NO waveform, so PPV is absent and SVV is charted only in a tiny PiCCO subset. Any MIMIC
  fluid-responsiveness study rests on a MAP-response PROXY (confounded by tone/pressors + saturated with RTM).
  Realistic labeled-AUC ceiling (~0.82-0.85, lit) only exists in cohorts WITH a real SV label. Confounding-by-
  indication caps the causal decision question at ~OR 1.35 (our structural ceiling).
- **VitalDB is the label-valid substrate** (has device SVV + arterial waveform + ECG + pleth in the same intraop
  cases) → a non-invasive-surrogate (ECG/pleth→SVV) is a clean SUPERVISED problem, not a confounded causal one.
  ECG→SVV is likely white space (pleth→SVV = PVI, known). This is the user-proposed and methodologically strongest thread.
- **Best MIMIC design if pursued = within-patient repeated-bolus "trait vs state"** (self-controlled, dodges the
  OR≈1.35 ceiling + named-index desk-reject; null-is-a-finding). Drop preference-IV (exclusion restriction fails,
  per our instrument sim). Target-trial emulation just reproduces CLOVERS/CLASSIC nulls.

## Fluid-responsiveness program — de-hyping + method lessons (COMPLETE)
- **COMPUTE THE LABEL'S OWN NOISE FLOOR before interpreting an ICC or proxy-AUROC.** Matched no-bolus
  windows (identical geometry/gating, no intervention) are the test. MIMIC continuous-CO (CCO 224842)
  no-bolus windows swing SD 14.2% and cross ±10% 21.4% of the time — indistinguishable from the 24.5%
  post-bolus "responder rate" (p=0.49); implied Δ-reliability ~0%. This converted "fluid response is a
  STATE" (ICC≈0) into "UNDETERMINED" (an ICC≈0 from a 0%-reliability label proves nothing) and softened
  "ΔMAP is near-useless" to a practical-only claim (mechanistic disattenuation is unidentifiable when
  both exposure and label are noisy). A "objective" label is not automatically a reliable one.
- **"No increment" ≠ "no signal."** The VitalDB ECG arm's increment-over-pleth null was AMBIGUOUS
  (redundant-equivalent vs empty). Fitting the STANDALONE model (ECG-alone) resolved it: ECG-alone ≈
  clinical baseline (0.632 vs M0 0.618), pleth-alone 0.733, equivalence REJECTED (−0.10 [−0.14,−0.06],
  outside ±0.03). Always test substitution, not just increment — they answer different questions.
- **ECG carries no standalone fluid-responsiveness (SVV) signal under general anesthesia** — GA
  suppresses respiratory sinus arrhythmia, so the ECG respiratory modulation pleth exploits isn't there;
  ECG and pleth features are uncorrelated (|r|≤0.17) and ECG doesn't rescue the low-perfusion zone.
- **The fluid-responsiveness label problem is structural and unsolved on accessible data:** VitalDB has
  SV truth (2s FloTrac) but no timestamped routine boluses (given by pressure bag/gravity; only 15
  rapid-infuser cases); MIMIC has ~100k timestamped boluses but a ~0%-reliability intermittent CO label.
  No accessible dataset has BOTH scalable boluses AND a reliable SV-response label. Prospective
  PLR/mini-bolus + continuous-CO capture would be required.
- **Preop labs add little** (+0.017 AUROC) to intraop-instability prediction over structural case
  variables (anesthesia type/ASA/age/department) — the preop-labs biomarker angle is weak.
- **Meta: for this domain, the honest deliverable is the rigorous NEGATIVE.** Confounding-by-indication
  (~OR 1.35 ceiling) + the label problem cap any positive; the program's contributions are clean,
  pre-registered, noise-floored nulls that rule out cheap surrogates and flag an unreliable common label.

## Chloride pseudohypochloremia mechanism REPLICATES cross-nationally (SICdb)
- SICdb (Austria, 8,912 paired patients) confirms the chloride electrolyte-exclusion mechanism: chem−BGA
  discordance ∼ total-protein slope −0.552 mmol/L per g/dL (z=−18.6), STRICTLY MONOTONE across protein
  quartiles, robust to a 10-min window (−0.495, z=−14.1), globulin-gap consistent (−0.642).
- **Quantitative mechanistic prediction confirmed** (a strong, hard-to-fake signature): Na:Cl protein-slope
  ratio 0.552/0.843 = 0.65 ≈ ion concentration ratio 100/140 = 0.71. Proportional plasma-water displacement
  predicts this; an analyzer/calibration artifact cannot manufacture a slope ratio matching the concentration
  ratio. Use this "does the effect scale with the analyte's concentration as the mechanism predicts" check as
  a discriminator between real electrolyte-exclusion and spurious offset.
- Chloride BGA reference (683) has NO sensor-reliability flag (sodium's 686 does) → chloride is cleaner than
  sodium on the reference-trust axis. Sex axis weak/non-robust (z=−1.8), not claimed (same as sodium).
- Chloride is now a VALIDATED coordinated 4th analyte alongside Na (Cl↓) and Ca (Ca↑) in the panel-wide
  indirect-ISE plasma-water-displacement bias — mechanism confirmed on two continents / two analyzer fleets.
  (SICdb has no race → confirms the protein MECHANISM; the racial endpoint remains MIMIC-specific.)

## Cycle 11 — second measurement-bias batch: novel-angle mining + two red-team catches
- **An EXACT ALGEBRAIC RESCALING of an existing finding carries ZERO incremental statistical evidence.** The
  osmolar-gap "propagation win" regressed the propagated bias on race and got z=2.77 — but that z is
  identical to SIX DECIMALS to the underlying sodium-bias regression (propagated = −2×Na-bias, same sample).
  Red-team reflex: compute the underlying regression alongside the "new" one; matching z ⇒ corollary, not
  confirmation. New empirical content can ONLY live where the DISTRIBUTION SHAPE matters (threshold
  crossings), not in a linear transform of the mean. (The propagates-vs-cancels PRINCIPLE is still valid and
  teachable — it pairs with the anion-gap cancellation — but it is a mathematical corollary of the Na finding.)
- **Widening a pairing window changes the COHORT, not just timing.** Even when a formula term cancels
  algebraically row-by-row (glu/BUN in the osmolar gap), loosening its window shifts which patients enter →
  composition effect can manufacture significance. The osmolar-gap flag disparity was significant only at a
  ±24h Na window; null at pre-registered ±1h and metabolically-tight ±6h. Re-test with each input pinned tight.
- **Threshold biases come in SYMMETRIC PAIRS.** A subgroup-miscalibrated formula over-flags at one threshold
  and masks at the other: corrected-Ca gives FALSE HYPERCALCEMIA (Black 13.3% vs White 8.0%, OR 1.77, survives
  red-team) AND masked hypocalcemia (doc 01). Same formula, same globulin mechanism, opposite clinical error.
  When you find a masking bias, test the over-flagging complement (and vice versa).
- **The false-hypercalcemia amplification is the FORMULA amplifying a real gap, not the formula discriminating.**
  Albumin distributions are near-identical by race and the correction magnitude is race-neutral within every
  albumin stratum; the amplification comes from a genuine +0.22 mg/dL higher raw total Ca at matched ionized,
  which a uniform additive correction pushes proportionally more Black patients over the cutoff. Scope: proven
  in the hypoalbuminemic 84%; a classification disparity, not demonstrated harm (no workup-order data).
- **Bicarbonate is a well-powered NEGATIVE CONTROL** (racial discordance CI excludes the Na/Cl effect sizes;
  no protein-tracking) → the electrolyte-exclusion bias is SPECIFIC to indirect-ISE plasma-water-displaced
  analytes (Na, Cl), not a generic "all electrolytes read low in Black patients" effect. Localizes the mechanism.
- **Occult hypoxemia clean-source note:** chartevents itemid 220227 is truly arterial (p25=94); labevents
  50817 mixes arterial+venous (p25=70) and must NOT be used for SaO2. Occult hypoxemia replicates Sjoding on
  the clean source (OR 2.45); the escalation-decision endpoint is non-testable in ABG cohorts (~53% already vented).
- **Meta (reconfirms cycle 10):** single-analyte mining yields mostly known/null (7/10 here); wins need novel
  angles; and even novel-angle "wins" can be corollaries (osmolar gap) — the red-team's rescaling/timing/
  composition checks are what separate a real increment from a restatement.

## IDEA_GATE — first demonstration (1 win / 3 depth ideas) + gate refinements
- **The gate raised win QUALITY, not obviously the raw rate on n=3** (1/3 ≈ blind rate). All three gave CLEAN,
  decisive answers (a confirmed magnitude prediction + two cleanly-falsified sharp predictions) — none of the
  messy RTM/confounded/demoted outcomes of blind batches. Falsifiable predictions produce GOOD nulls.
- **The gate's biggest value is UPSTREAM and invisible in the run count:** the kill list cheaply eliminated ~15
  gate-failures (no ground truth / already-published) BEFORE compute. Efficiency gain = losers not run, not
  wins found. Measure the gate by compute-saved-on-losers, not just hit rate on the chosen few.
- **GATE REFINEMENT — threshold-complement moves depend on the BASELINE ANALYZER OFFSET direction, not just the
  racial differential.** Masked-hypernatremia nulled because MIMIC chem Na OVER-reads (positive offset) → it
  over-flags, not masks, the upper tail. Before assuming a masking bias has a symmetric upper-tail twin, check
  the sign of the raw (not race-differential) offset. Add to the gate's pre-mortem.
- **GATE REFINEMENT — a "sharper within-patient version" of an already-confirmed population effect often fails**
  because individual-level measurement noise attenuates the shared-driver slope (Na+Cl fingerprint: population
  Cl:Na protein-slope ratio 0.65 in SICdb, but within-patient bias-vs-bias slope only 0.25 — Cl discordance is
  noisier / less protein-mediated at the patient level). Population dose-response ≠ patient-level fingerprint.
- **STRATEGIC SIGNAL: the electrolyte-exclusion seam is NEAR-EXHAUSTED for novel DEPTH wins.** All 3 depth ideas
  confirmed the core mechanism but 2 failed to EXTEND it. The remaining depth wins are negative controls
  (K, bicarbonate) — valuable but incremental. Fresh flagship potential is in NEW SEAMS (glucose-meter Hct
  interference, now data-live: fingerstick 225664 populated 255k+ rows). Pivot compute to the new seam.

## Discriminator calibration — the "subgroup driver must vary IN THE COHORT" lesson (glucose-meter seam)
- **A subgroup driver that differs in the GENERAL POPULATION can be INVARIANT in the analysis cohort — silently
  killing the disparity angle.** POC glucose-meter Hct interference: the Hct dose-response is clean and
  negative-controlled (−0.449 mg/dL/%Hct, z=−11.9; plasma-cal POC slope 0.00), and anemia→false-hyperglycemia
  is a real mechanism-confirmed WIN. But the RACIAL framing failed its pre-registered specificity control
  because Black and White ICU patients have IDENTICAL hematocrit (29.8 vs 29.7) — anemia is near-universal in
  the ICU, so it cannot sort by race here; the real +4 mg/dL Black offset is NOT Hct-mediated.
- **DISCRIMINATOR REFINEMENT (add to the "subgroup driver" signal):** don't just verify the driver differs by
  subgroup in the literature — verify it has VARIANCE BY SUBGROUP IN THE SPECIFIC COHORT (a 2-min check:
  mean driver by subgroup in the actual data). If the cohort flattens the driver (ICU anemia, ICU acuity),
  the disparity angle is dead even if the mechanism is real. The mechanism finding can still stand on the
  driver's continuous axis (here: anemia→false-hyperglycemia), just not as a subgroup-disparity flagship.
- **CALIBRATION ENTRY (predicted→actual):** glucose-meter seam predicted HIGH → actual PARTIAL (mechanism won,
  racial flagship confounded). The make-or-break falsifiable prediction (Hct slope) + the mandatory specificity
  control both did their jobs — the control killed the overreach, exactly as designed. Running tally of the
  discriminator's first use: potassium-control HIGH→WIN, masked-hypernatremia HIGH→NULL, Na+Cl-fingerprint
  MED→NULL, glucose-meter HIGH→PARTIAL. Strongest predictor of a clean result remains a sharp falsifiable
  prediction + a real negative control; "documented subgroup driver" needs the in-cohort-variance check.

## Discriminator calibration — the driver needs RANGE (not just variance) in the cohort (new-triple search)
- **COHb → pulse-ox nulled the same way glucose-meter did — the driver was documented in the general population
  but FLAT in the cohort.** Carboxyhemoglobin biases SpO₂ upward, but in the ICU COHb is uniformly low (mean
  1.1%, max ~7%; severe CO poisoning is triaged to the ED/hyperbaric, never reaches the routine ABG cohort) →
  no dynamic range → no dose-response detectable, regardless of mechanism validity. This is the DOSE-RANGE
  failure, distinct from the VARIANCE-BY-SUBGROUP failure (glucose-meter): a dose-response needs the biasing
  agent to SPAN a range in the cohort; a disparity needs it to DIFFER by subgroup in the cohort. Both are
  in-cohort distribution checks; check both before scoring a driver.
- **Clean consolation sub-result:** COHb is racially invariant in the ICU (Black≈White) → it cannot be the
  confounder behind the Sjoding occult-hypoxemia racial gap. A "null with range" still ruled a rival mechanism
  OUT — negative-result value.
- **The WIN that proves the rule — thrombocytosis → pseudohyperkalemia.** Predicted MED-HIGH → WIN. Everything
  the two misses lacked, this had: a clean serum-vs-plasma ground-truth reference AND a driver (platelet count)
  with ABUNDANT in-cohort range (into the millions). Platelet slope **+0.052 mEq/L per 100k (z=22.9)**, strictly
  monotone to +0.79 at platelets >1000k; false-hyperK 1.6%→28% across platelet bands; the **WBC arm is null**
  (localizes the mechanism to platelets, not generic cellularity). NB the RACIAL false-hyperK gap replicates
  (Black 6.6% vs White 3.3%) but is NOT platelet-mediated (survives platelet adjustment) — a separate pre-analytic
  disparity (hemolysis/draw), so the win is the platelet dose-response, not a racial flagship.
- **DISCRIMINATOR PROMOTION:** "does the driver have the needed distribution IN THE ACTUAL COHORT?" is now the
  THIRD strong signal in `IDEA_GATE.md` (was a supporting one). Two components: (a) dynamic RANGE for a
  dose-response; (b) VARIANCE BY SUBGROUP for a disparity. After 7 scored ideas, the two HIGH misses (glucose,
  COHb) and the MED-HIGH win (thrombocytosis) are ALL explained by this one signal — it is the biggest recurring
  calibration error (over-scoring a driver on general-population evidence without the 2-min in-cohort describe).

## External-validation cycle — the calcium flagship in eICU (doc 12); what hardened, what to watch
- **Pick the CKD-ROBUST direction as the headline when two thresholds exist.** The corrected-Ca bias has two
  endpoints: masked hypocalcemia (lower) and false hypercalcemia (upper). In eICU, restricting to creatinine<1.3
  the FALSE-HYPERCALCEMIA OR held (2.57→2.56, p<0.001) but MASKED-HYPOCALCEMIA collapsed (1.66→1.24, ns) — the
  lower-threshold direction was largely renal/phosphate-mediated. When a case-mix confound (here CKD, far more
  prevalent in Black ICU patients: creat 1.40 vs 1.03, dialysis 13.4% vs 3.3%) differentially loads one
  threshold, lead with the direction that survives adjustment. Build the confound into the PRIMARY estimate, not
  a footnote (the red-team's demand).
- **"Adjusting for the mediator erases the effect" is CONFIRMATION, not refutation — pre-empt the reviewer.**
  Total protein is +0.47 g/dL higher in Black patients and adjusting for it collapses the race coefficient to
  ns. A hostile reviewer will call this "debunked." It is the mechanism (globulin→protein-bound Ca) operating
  as predicted; total protein is a MEDIATOR on the causal path, not a confounder. State this explicitly and
  frame the mediator-adjustment as a positive-control mechanism check. (Myeloma exclusion unchanged → it's
  broad population-level, not a rare-paraprotein artifact.)
- **Filter-sensitivity is a required reproduction step for any EHR result with data-entry junk.** Re-run under
  ≥3 filter regimes (hard physiologic / strict / loose); a real effect is stable or STRENGTHENS under stricter
  bounds (ours: OR 2.65/2.79/1.71). If it only appears under one specific filter → red flag. Also report the
  raw event 2×2 (ours 49–71 events >>30) to kill the small-cell attack.
- **Cluster-robust pooled ≠ per-site validated.** A significant hospital-clustered pooled estimate (+2.67pp,
  z=5.46) can coexist with a non-significant inverse-variance meta across sites (+0.57pp, p=0.28) when a few
  high-volume null hospitals dominate the precision weights. Do NOT write "validated across N hospitals" off a
  pooled SE; show a forest plot and say the per-site check is underpowered by design. Honesty here is cheap and
  a reviewer WILL check it.
- **Match the external cohort to the ENDPOINT, not just the analyte.** eICU has race + total + ionized calcium
  (validates the calcium measurement bias) but NO blood-gas sodium/chloride (cannot validate the Na/Cl
  discordance) and its IV-calcium repletion lives in an un-downloaded `medication` table (cannot test the
  treatment consequence — infusionDrug caught only 316/73,547 stays). Before launching an external-validation
  run, verify the specific ground-truth reference AND the consequence variable exist in that cohort's tables,
  not just the analyte. The consequence test moves to MIMIC (inputevents/repletions.csv present).
- **"DYNAMIC/TRAJECTORY" EHR FEATURES OFTEN JUST RE-ENCODE LEVELS — and charting resolution caps true dynamics
  (EX-2 NO-GO).** Testing whether SBT vital-sign DYNAMICS add value beyond static predictors for reintubation:
  static+dynamic beat static (Δ+0.012, p<1e-6) but the gain was entirely LEVEL re-encoding (RR_mean/HR_mean top;
  RR-variability near-bottom). **Diagnostic test: strip all `*_mean`/`*_end` LEVEL features and check if pure
  slope/variability retains signal — here it fell to ~chance (0.596), and the marginal gain collapsed at a wider
  window (p=0.88) and on excluding the sickest (acuity confound, not physiology).** Second hard limit: routine
  EHR charting is q1–2h (~2 points/channel in a 2h window) — **too coarse for breath-by-breath / high-frequency
  variability** (the WAVE RR-variability signal). True SBT-timescale dynamics need WAVEFORM data (MIMIC-IV-
  Waveform), not charted vitals. Tempers the "trajectory beats snapshot" enthusiasm (from the sepsis design):
  trajectory helps only when charting is DENSE relative to the physiologic timescale; for fast dynamics on sparse
  charting, "dynamic" features are just a fresher level measurement. Always run the strip-the-levels test before
  claiming a trajectory finding.
- **STRATEGIC — the measurement-bias-propagation seam in PUBLIC ICU DATA (MIMIC/eICU) is ACTIVELY MINED; NOVELTY
  is now the binding constraint, not feasibility.** Two consecutive fresh propagation-maps (T1 temperature-site,
  H1 HbA1c) died because the exact idea was already published IN THESE EXACT DATASETS by well-resourced groups
  (Celi/MIT-LCP, Bhavani, Wong, Sjoding, Seymour — e.g. Matos 2025 PMID 40236438 hidden-fever→SEP-1 in
  MIMIC+eICU). Calcium won because the corrected-Ca-by-race angle was a rare unmined gap. **Implication: run the
  novelty pre-screen FIRST and hard — if the mechanism is textbook AND the dataset is MIMIC/eICU, assume one of
  these groups may have done it; search their recent output specifically.** Higher-white-space directions when
  MIMIC/eICU novelty is scarce: (a) finalize/extend the calcium win (a real novel externally-validated finding);
  (b) LESS-MINED data — SICdb-primary findings, VitalDB waveforms, INSPIRE (Korean surgical) — angles these
  groups don't work; (c) the GPU-gated EEG-foundation-model mission (genuine white space, compute-blocked); (d)
  accept a confirmatory/replication contribution. Do NOT keep grinding textbook-mechanism MIMIC propagation-maps
  expecting novelty.
- **THE GROUND-TRUTH REFERENCE MUST BE CLEAN FOR THE SPECIFIC MECHANISM, not just nominally present (HbA1c
  NO-GO).** HbA1c-RBC-lifespan → diabetes misdiagnosis needs a reference for *chronic* glycemia. Glucose exists
  at scale in MIMIC, but in-hospital glucose is STRESS-confounded (dextrose/critical-illness hyperglycemia ≠
  chronic glycemia), and the mechanism-clean reference (fructosamine/glycated albumin) has 0 rows. So the
  "matched-glucose" conditioning is not matched on the thing the mechanism concerns. **Diagnostic fingerprint of
  a confounded reference: the linear-adjustment estimate UNDER-shoots the mechanism while the stratified/matched
  estimate OVER-shoots it** (HbA1c: linear +0.2pp vs stratified 1–2pp) — the two disagree because the
  conditioning variable carries residual confounding. Before scoring a reference as "present," ask: is it clean
  for THIS mechanism, or confounded by the acute-illness state? (Adds to the co-occurrence check.)
- **PROPAGATION-MAP ENDPOINT MUST BE A *FREE* (UNCONTROLLED) VARIABLE — not one in a titration feedback loop
  (vancomycin NO-GO).** A bias→decision→outcome propagation only produces a measurable downstream disparity if
  the ENDPOINT is not actively titrated back to target by the care system. Vancomycin: creatinine underestimates
  renal impairment in low-muscle women → CG overestimates CrCl ~29% → mechanism predicts an 18–35% higher trough;
  OBSERVED only 3.5–10% (a 5× UNDER-shoot). Reason: the vanco trough is TDM-controlled — clinicians measure it
  and re-titrate both sexes to target, so the feedback loop CORRECTS the upstream bias and severs the
  decision→outcome link. **New pre-run check for any propagation-map: is the endpoint actively titrated to a
  target (drug trough, glucose-on-insulin, INR-on-warfarin, MAP-on-pressors, ventilator SpO₂-target)? If yes, a
  real upstream bias will read strongly ATTENUATED — pick a FREE endpoint instead (a one-shot classification/order
  that is not re-titrated — e.g., the calcium WORKUP order, which worked precisely because workup isn't titrated
  to a target).** This is WHY the calcium propagation succeeded (workup = free) and vancomycin fails (trough =
  controlled).
- **The mechanistic-magnitude check catches BOTH failure directions.** OVER-shoot (observed ≫ predicted → C12-1,
  cohort-specific inflation/confounding, won't externally replicate) AND UNDER-shoot (observed ≪ predicted →
  vancomycin, feedback-controlled/attenuated endpoint, no clean disparity to report). Compute the effect the
  mechanism predicts from first principles and compare BEFORE claiming; a mismatch in either direction is a red
  flag. Only observed ≈ predicted is a mechanistically-credible propagation worth building.
- **INTERNAL ROBUSTNESS ≠ EXTERNAL REPLICATION — and a mechanistic-magnitude sanity check would have flagged it
  (C12-1 tempered).** The occult-hypoxemia→SF/ARDS/SOFA propagation passed every INTERNAL gate (cluster-robust,
  one-pair-per-subject, FiO₂/nonlinearity/PEEP robustness, novelty) — then FAILED eICU external validation: the
  biomarker bias (occult hypoxemia) replicated cleanly and universally (OR 2.03 vs 2.09, 152 hospitals), but the
  score-level propagation did not (Tests 1–3 null/wrong-sign). **The tell was available internally and I missed
  it:** the differential pulse-ox bias (~+1.15 SpO₂ ÷ FiO₂ ≈ **+2 SF units**) MECHANISTICALLY predicts a small SF
  effect, but MIMIC's Test 1 gave **+6.87 — ~3× the mechanism's prediction.** When an observed effect is several
  times larger than the mechanism can produce, that gap is a red flag for cohort-specific inflation (FiO₂
  charting/sourcing, PF-adjustment specification, residual confounding), NOT a strong finding. **New pre-external
  check: compute the effect the mechanism PREDICTS from first principles and compare to the observed magnitude; a
  large over-shoot means it probably won't replicate.** Also: a propagation-map's biomarker-bias core replicating
  does NOT mean its score-propagation replicates — they are separate claims; the score effect needs classification
  HEADROOM (moderate-severity patients), which a uniformly-sick external cohort (eICU median PF 160) can erase.
  Net: external validation is load-bearing and caught an over-claim internal robustness passed. C12-1 downgraded
  from flagship to a dissociation/bounded finding.
- **HIGHEST-HIT TEMPLATE — "propagation-map into a decision-score" (with a REPLICATION caveat).** The
  best-hit-rate idea shape this session: take a bias ALREADY externally established (occult hypoxemia;
  indirect-ISE displacement; globulin binding), find a consequential FORMULA/SCORE that consumes the biased input
  (SpO₂/FiO₂ → ARDS-Berlin class + SOFA-resp; albumin-corrected Ca; osmolar gap), and quantify the racial
  MISCLASSIFICATION of the score at matched TRUTH. **CAVEAT (post-external-validation): the propagation MAGNITUDE
  is cohort-specific — the CALCIUM propagation externally replicated (eICU, doc 12) but the OCCULT-HYPOXEMIA
  propagation did NOT (C12-1b: score-level Tests null in eICU though the biomarker bias replicated).** So the
  template reliably surfaces a real signal, but whether the SCORE-level harm generalizes depends on classification
  headroom + the mechanistic magnitude (see the internal-robustness≠external-replication lesson above). Always
  externally validate the SCORE claim, not just the biomarker bias. Why it beats
  harm-chains: the endpoint IS the misclassification of a score that drives the decision (trial enrollment,
  ECMO, crisis triage), so you never need the elusive terminal-harm cell and you dodge the paired-reference
  selection wall (next lesson). Two execution notes that made it clean: (1) reframe a racial score-effect as a
  **tail/threshold-crossing** effect, not a population-mean shift — SF is globally conservative (curvilinear
  ceiling), the racial harm is only in the under-scoring tail, and this is the ONLY framing compatible with
  opposite-direction whole-score findings (Ashana/Miller: whole-SOFA over-predicts for Black patients); (2)
  **predict TIER, not just win/loss** — a clean novel propagation finding is JAMA-IM/AJRCCM/Lancet-Resp tier,
  not automatically NEJM/Nature; over-claiming tier is its own calibration error.
- **TEMPLATE-LEVEL LESSON (load-bearing) — the paired-reference cohort PROVES the measurement bias but
  structurally CANNOT prove its downstream harm.** Two independent consequence chains now failed the SAME way:
  calcium false-flag → unnecessary workup (ledger 18/18b) and potassium false-hyperK → insulin/D50 →
  iatrogenic hypoglycemia (C12-3). Both showed a STRONG measurement-mediated ACTION link (the biased value
  drives the clinical action holding the true value fixed — calcium workup OR 1.17–1.42; potassium treatment
  **chem-K OR 2.34 per mEq/L, p=1.7e-61, with true bg-K held fixed and NS**) AND a cleanly REPLICATED racial
  EXPOSURE disparity (~2×), but an EMPTY / underpowered TERMINAL-HARM cell (workup: 4–8 Black events;
  hypoglycemia: 0/4 false-flag-treated). The common cause is SELECTION, not chance: the cohort that HAS the
  ground truth drawn (ionized Ca, blood-gas K) is exactly the high-acuity ICU setting where clinicians SEE the
  true value and are protected from acting on the artifact. The realized harm happens where ONLY the biased
  value exists — floor/ED/outpatient with no paired gas/ionized — which the paired design cannot observe by
  construction. **Strategic implications:** (1) From a paired design, the defensible consequence endpoint is the
  ACTION-level measurement-mediated link + the exposure disparity — report those as the finding; do NOT expect
  the terminal hard-harm cell to close, and do NOT keep spending compute chasing it. (2) To show realized harm,
  you need a SINGLE-METHOD cohort (only the biased value present) with an external/instrumental design, or a
  dataset that captures floor/ED action on a lone chemistry value. (3) Frame realized harm as
  mechanistically-implied (action link × exposure disparity), explicitly bounded — like the calcium manuscript
  does. This is why the calcium paper lands as an eGFR-style *reclassification/action* equity finding, not a
  mortality finding. Stop running paired-design terminal-harm chains expecting closure.
- **FEASIBILITY REFINEMENT — an itemid existing ≠ the paired reference being co-ordered at scale.** C12-2
  (pre-analytic lactate) died an infeasibility null: chem lactate (53154) and blood-gas lactate (50813) both
  exist, but chem lactate is a rare floor order (104 rows) and bg lactate a high-volume POC order — they are
  essentially never co-drawn (1 paired patient at ±60 min). A two-method ground-truth design needs the two
  methods CO-ORDERED in the same patients within the pairing window, not merely both present in the dictionary.
  The 2-minute feasibility grep must count paired co-occurrence, not itemid existence (same failure class as the
  eICU `medication` table — conceptually present, not populated for the design). Add to the pre-run checklist:
  "paired-reference co-occurrence ≥ target N within the window?" — a cheap kill before compute.
- **The NEJM bar for this program = the eGFR race-coefficient analogue (Vyas 2020), not a hard outcome.** The
  measurement bias + misclassification + fixable-formula story IS a complete measurement-equity paper if
  externally validated and mechanism-nailed; the hard arrhythmia/mortality chain stays a lead (doc 05: eICU
  mortality does not replicate, event counts fragile). The remaining NEJM-completing lever is a
  MEASUREMENT-MEDIATED consequence — repletion is not mediated (doc 05), so the open test is whether a false-high
  corrected Ca triggers differential UNNECESSARY workup (PTH/SPEP) by race, conditioned on normal ionized.
- **BOUNDARY-CONDITION LESSON — a mechanism-driven ENDPOINT can fail to replicate in a setting where the
  mechanism's precondition is absent, without contradicting the mechanism.** The calcium racial
  false-hypercalcemia endpoint replicated across two US ICU cohorts (MIMIC, eICU) but did NOT replicate in the
  Stanford MC-MED emergency-department cohort (paired N≈931; Black β=−0.05, z=−0.47; false-hyperCa 8/922 = 0.9%,
  zero events in the Black arm). Root cause is not a contradiction: the corrected-Ca formula's over-correction
  only bites when a LARGE albumin add-back is applied, i.e. in hypoalbuminemia (~84% of the ICU extraction). The
  ED cohort's mean albumin is near-normal (~3.86 g/dL), so the formula barely moves the value and there is no
  racial gap to amplify. **Discriminator upgrade:** when the endpoint depends on a formula/correction, add the
  formula's OPERATING PRECONDITION (here: hypoalbuminemia) to the external-validation site-selection checklist —
  don't validate a hypoalbuminemia-driven endpoint in a normal-albumin population and read a null as a failure.
  The correct move on a precondition-absent null is to SCOPE the endpoint honestly (racial endpoint = inpatient
  hypoalbuminemic setting) and keep the mechanism claim (5 cohorts) intact — exactly as done for C12-1. Also:
  n=69 in the smallest race arm cannot power an OR~1.8 effect, so even a directionally-consistent null there is
  uninformative — pre-check minimum-arm power before counting a site as a replication test.
- **CORRECTION/FIX EVALUATION — a proposed correction that recovers missed cases can be a NET null if it destroys
  specificity; evaluate the fix on BOTH axes and reframe the actionable message around the ground truth.** The
  albumin-corrected anion gap recovers hypoalbuminemia-masked lactic acidosis (sensitivity 93.9%→99.7% in
  hypoalb) but craters specificity (44.9%→8.1%) — reproducing the published Dinh-2006 "no advantage" null and the
  EMCrit/Carvounis circularity critique (corrected-AG r≈0.11 with true unmeasured anions). The real, novel result
  survives as a **severity-stratified blind-spot gradient** (missed-acidosis RR 8.95 severe-vs-normo albumin, a
  gradient Dinh's POOLED AUC washed out) whose actionable message is NOT "apply the correction" but "in the
  high-driver stratum (low albumin), the reassuring-normal score is unreliable — measure the ground truth
  (lactate) directly." Two reusable rules: (1) whenever you propose a corrected formula as the fix, compute its
  specificity cost in the high-driver stratum before claiming it — a sensitivity-only win is not a fix. (2) When a
  novelty screen surfaces a published POOLED null on your comparison, the only surviving wedge is
  driver-stratification + a decision endpoint; re-scoring the pooled comparison just re-derives the null.
- **NOVELTY GATE OUTRANKS FEASIBILITY GATE for binding-correction ideas — score novelty FIRST.** K-T4 (Free
  Thyroxine Index vs measured free T4) passed feasibility handsomely (6,801 co-drawn pairs) but was dead on
  arrival: the TBG→FTI bias is the textbook reason direct free-T4 assays replaced the index, and free T4
  outnumbers total T4 5:1 so there is no live "biased formula drives decisions" endpoint. The classic
  total-vs-free binding corrections (FTI, adult corrected-calcium, Sheiner-Tozer phenytoin) are ALL textbook
  mechanisms — for this idea class, run the 2-minute novelty+decision-relevance check before spending the
  feasibility grep, not after.
- **CONDITIONING-ON-MEASURED-TRUTH trap (sharpened paired-design lesson) — an analysis conditioned on the
  ground-truth having been measured CANNOT speak to the decision that OMITTING the ground-truth would drive.**
  The anion-gap masking cohort (n=57,761) is defined by chem-panel↔lactate PAIRS → every patient already had a
  lactate ordered. So it can quantify how often a normal AG co-occurs with true acidosis, but it structurally
  cannot show that a reassuring-normal AG ever *stopped* a clinician from ordering lactate — that population (AG
  normal, lactate NEVER drawn, truly acidotic) is excluded by the sampling frame, and its outcome is undefined
  (no lactate = no ground truth to label "missed"). The decision/harm endpoint lives exactly in the cell the
  paired design deletes. This is the same wall as C12-1 (occult hypoxemia: the harm happens where only the biased
  value exists) — now stated as a general rule: **if the exposure is "a biased test looked normal" and the harm
  is "the confirmatory test was skipped," the confirmatory-test-skipped patients are unobservable in any
  paired-reference cohort; you need a single-method cohort + an instrument/natural experiment (order-set change,
  provider practice variation), not more paired data.** A full re-download of a paired-reference table does not
  fix an identification problem — it buys more of the same unidentifiable data.
- **TAUTOLOGICAL DIRECTION vs EMPIRICAL MAGNITUDE — when a finding's direction is guaranteed by the formula you
  used to define the counterfactual, the ONLY empirical content is the magnitude-at-a-threshold in a messy real
  cohort; grade novelty accordingly.** The AG-masking gradient's sign is pure algebra (albumin is an unmeasured
  anion; lower albumin mechanically lowers AG — the corrected-AG formula IS that identity), so "hypoalbuminemia
  masks AG" is not a discovery. What is empirical: the threshold-crossing RATE (1%→8.7%), which depends on the
  joint distribution of lactate/albumin/other unmeasured anions and is not derivable from the formula. Rule for
  the discriminator: if you're using a correction formula as the counterfactual/ground-truth, the mechanism claim
  is tautological — the finding must earn novelty from a magnitude, a decision endpoint, or a disparity, never
  from the direction. If it can't, it's confirmatory.
- **CORRECTION-FACTOR REFINEMENT is futile when the corrected quantity poorly tracks the ground truth — check
  corrected-vs-truth CORRELATION before investing in a "better formula."** PIC pediatric: the albumin/Ca binding
  slope is genuinely age-dependent (0.80 infants → 0.93 toddlers → 0.72 adolescents), but an age-corrected
  calcium formula did NOT beat adult Payne-0.8 on reclassification against ionized (net worse: fixes 74/breaks
  141) — because albumin-corrected Ca correlates with ionized only at r≈0.47 in children, barely above raw total
  (0.467). When the corrected value tracks the ground truth that weakly, changing the correction slope just
  reshuffles misclassifications; no slope can rescue a surrogate near its calibration ceiling. Pre-run check for
  any "refine the biased formula" idea: compute r(corrected, truth) vs r(raw, truth) FIRST — if the correction
  barely improves correlation, formula-refinement is dead on arrival and the only real message is "measure the
  ground truth directly." This is the fourth consecutive result (T4, anion-gap, Hgb, PIC) where the reachable
  measurement-bias/formula-refinement angle returns confirmatory/null — the seam's actionable output is
  consistently "measure the ground truth," not a new correction. Treat further correction-refinement ideas as
  negative-EV unless they clear this correlation pre-check.
- **EXPOSURE DISPARITY ≠ ACTION HARM — a subgroup being flagged more often by a benign threshold does NOT imply
  they are over-acted-upon; check the action direction, it can reverse.** MC-MED BEN: Black ED patients are
  flagged low-ANC 1.85× more (real exposure disparity from a benign Duffy-null left-shift), but at MATCHED low
  ANC they received LESS reactive workup (repeat-CBC 9.8% vs 21.5%, isolation 41% vs 50%, culture 50% vs 63%) and
  lower admission — the opposite of the hypothesized over-workup harm, most parsimoniously appropriate BEN
  recognition. Two lessons: (1) an exposure/misclassification disparity is only half a story; the downstream
  ACTION must be measured directly and can run the other way. (2) ED action layers (culture/isolation/admit) are
  massively confounded by presenting illness (low-ANC ED patients are septic), so "flag → action" association is
  really "sick → action" — the order-after-result timing handle helps but does not remove presentation
  confounding. A clean action-harm claim needs the flag to be the ONLY plausible driver of the action, which the
  ED rarely provides. (BEN exposure disparity itself is real but textbook — not top-tier.)
- **OVERNIGHT META (4-strike MC-MED ED hunt) — the ED "action layer" does NOT reliably break the measurement-bias
  harm-observability wall.** The thesis (harm is observable in ED recorded actions where ICU paired data can't see
  it) failed across 4 candidates for consistent reasons: BEN (exposure disparity real but action REVERSED —
  appropriate recognition; presentation-confounded), glucose-Hct (modern Hct-corrected devices null the
  mechanism), occult hypoxemia (no arterial SaO2 reference in ED — venous only), triage-ESI (disparity real but
  fails to validate against the hard bounce-back outcome + scooped). Root cause: attaching a HARM/ACTION endpoint
  to a disparity keeps failing because ED actions are presentation-confounded, reverse, or don't validate. **The
  calcium flagship won precisely because it STOPPED at the observable RECLASSIFICATION endpoint and never needed
  downstream harm.** Revised search rule: hunt clean non-tautological RECLASSIFICATION findings (subgroup driver +
  ground-truth reference + observable threshold-crossing) — do NOT chase action-harm chains, in the ED or the ICU.
  Corollary: modern (2020s) cohorts attenuate device/assay-interference mechanisms found in older data (bound such
  findings by era); and always verify the GROUND-TRUTH REFERENCE exists in the target setting (arterial vs venous)
  before running — reference-mismatch is a cheap pre-run kill.

- **Observational bedside decision-TOOLS die to four predictable knives — pre-run for all four (A-line tool, 2026-07-08).**
  We tried to turn the C8 measurement finding into a validated pre-operative arterial-line decision *score*. A full
  TRIPOD-grade re-analysis + hostile-reviewer red-team killed the standalone tool. The four knives, each of which
  should be a CHEAP PRE-RUN CHECK for any future decision-tool idea:
  1. **Realized-feature leakage.** "Long case >4h" used *realized* operative duration — a look-ahead (long cases
     run long partly *because* of the intraop events that cause the outcome). Removing it dropped held-out AUC
     0.68→0.57 (it was doing nearly all the work). RULE: every predictor must be knowable at the moment of the
     decision; realized intra-op durations/counts are leakage.
  2. **Failed external validation masquerading as "attenuation."** Frozen score AUC 0.546 in VitalDB with
     non-monotone calibration. Do NOT explain a near-null external AUC away with a case-mix story unless you can
     demonstrate the mechanism; TRIPOD-AI calls 0.55[0.51,0.58] a FAILED validation, full stop.
  3. **Composite-outcome severity laundering.** A "harm-associated" composite (AKI/death/MINS/lactate) gave a
     flattering AUC (0.68) that was just "sick patient, big surgery" — proven by: the score predicted harm BETTER
     in patients WITHOUT the mechanism (missed-hypotension=0, AUC 0.708) than with it (0.646). RULE: test whether
     the score predicts the outcome THROUGH the claimed mechanism, not around it (stratify by the mechanism flag).
  4. **Verification/selection bias (the unfixable one).** The target (cuff-missed hypotension) is observable ONLY
     in patients who already got an arterial line, so the derivation cohort categorically excludes the deployment
     population (un-lined gray-zone patients). No re-analysis of the same data fixes this — only a prospective
     trial in the un-lined population does. RULE: if the outcome requires the very intervention you're deciding
     about, the observational tool is structurally un-validatable; go straight to the trial design.
  **What survived and why:** the C8 *measurement* finding (device physics, externally validated in eICU) + a
  **model-free** action (cuff cycling ≤2-3min + treat MAP<70 — no prediction needed, 57%→75% sensitivity). GENERAL
  LESSON: when a measurement/reclassification finding is solid but the "who-to-treat" prediction layer fails,
  the durable deliverable is the MODEL-FREE correction + a trial protocol — not an overfit score. Modest-AUC +
  good-calibration + positive-DCA is NOT enough to call something a validated tool if it leaks, fails external, is
  severity-confounded, or is selection-biased. Honest demotion beats a tool that dies in peer review.

- **"Survives adversarial review" is a CONVERGENCE test, not a one-shot (A-line tool, 2026-07-08).** Ran 3
  independent hostile-reviewer rounds (sonnet) on the same package. The signal that a finding is real is the
  SEVERITY TRAJECTORY: round 1 FATAL (leaking score, causal overclaim) → round 2 MAJOR (fixable) → round 3
  "completeness gap, not validity gap." If each round surfaces smaller issues, it's converging (publishable); if
  each round finds new fatal flaws, it's not. Two operational rules that emerged: (1) When a reviewer calls a
  result "tautological," the fix is often a REFRAME + a confirmatory test, not a rebuttal — e.g. the cuff-vs-art
  harm attenuation looked like a second finding; conditioning outcome on CONTINUOUS true arterial burden collapsed
  the cuff OR to 1.05 (null), which *confirms* it's the quantified consequence of the measurement error and is
  STRONGER than the original framing. (2) For a mechanism-confounder attack (here: is the low-pressure cuff
  over-read device-physics or vasopressor-vasoconstriction?), the between-group stratified analysis is
  confounded-by-indication; the design reviewers actually credit is the WITHIN-PATIENT crossover at matched
  true-value (on-vs-off bias diff was null at matched MAP → device physics). Always reach for the within-subject
  design when the confounder is a patient-level phenotype. Also: report magnitude honestly (VitalDB +30.6 vs eICU
  +13.1 mmHg = "direction + order-of-magnitude," not "identical") — reviewers do the arithmetic.

- **CHECK A MEASUREMENT CHANNEL'S PHYSIOLOGICAL RANGE BEFORE building a discordance/reclassification study on it
  (etCO₂ kill, 2026-07-09).** Spent a full discordance + dead-space-mechanism analysis on INSPIRE etCO₂-vs-PaCO₂
  "occult hypercapnia" before discovering the `etco2` channel is **hard-clipped to [23,41]** (3.5M readings, max
  41, 0.00% >45) — a data/units/binning artifact, not physiology. The whole "etCO₂ under-reads, gap widens with
  hypercapnia" pattern was the ceiling. A 30-second `np.percentile(channel,[0,1,50,99,100])` at the START would
  have killed it instantly. RULE: for every new signal used as either the test or the reference, first print
  min/p1/median/p99/max and confirm it spans the physiological range AND isn't clipped/binned. The C8/calcium
  wins all used channels whose ranges I'd implicitly trusted (BP, Ca) — etCO₂ was the first clipped one. Corollary
  now applied downstream: SpO₂ idea (#2) uses the SAME INSPIRE vitals source → range-check spo2 AND sao2 before
  trusting them. Also: a too-clean result (0 detected / 100% missed / a perfectly flat curve) is itself a
  clipping/artifact tell — investigate the raw distribution before believing an extreme effect.

- **A within-category outcome signal needs a NEGATIVE-CONTROL category before you claim it's category-specific
  (EEG IIC-mortality, 2026-07-09).** Built the outcome-anchored EEG study (does the pattern's morphology predict
  mortality WITHIN one expert IIC label, resolving the gray zone by outcome?). Got a modest cross-site-consistent
  within-GPD/LPD signal (~0.59, age=0.50) and nearly wrote it up as "promising/non-me-too." The negative control
  killed it: classical EEG predicts mortality WITHIN the LOW-RISK slowing pattern at **0.73 — higher** than within
  GPD/LPD. So the signal is GENERIC encephalopathy-severity (predicts death in any pattern), NOT pattern-specific
  harm. RULE: whenever the claim is "feature X carries information SPECIFIC to condition A," run X on a control
  condition B where it should NOT — if it works there too (or better), the signal is generic/confounded, not
  specific. Cheap, decisive, and it inverts the interpretation. Also: "cross-site consistent, both directions,
  age-null" felt convincing but was NOT sufficient — a generic severity signal is also cross-site consistent.
  Same family as the etCO₂/SpO₂ channel-range kills: build the disconfirming test into the design, don't wait for
  the red-team.

- **For any "labeled event happened LATER" outcome, SURVEILLANCE/ASCERTAINMENT intensity is the dominant confound —
  adjust for monitoring before believing any predictor (EEG seizure-prognosis kill, 2026-07-09).** Built a
  single-site seizure-progression model; frozen CBraMod added a significant, seed-stable +0.067 AUC over
  age+category (0.591→0.654) — the program's first foundation-model win, nearly written up as "promising." The #1
  red-team test killed it: the outcome `sz_next` = "a SEIZURE epoch was labeled ≥1 day later," which is dominated by
  **how long/continuously the patient was monitored** — monitoring intensity alone predicts it at 0.829, CBraMod's
  embedding encodes monitoring type (→any-cEEG 0.773), and the +0.067 collapses to +0.001 (null) once monitoring is
  a covariate. RULE: whenever the outcome is "event was detected/labeled during followup," the probability of
  DETECTION scales with surveillance (cEEG hours, #labs, #imaging) — always build a surveillance-intensity covariate
  and check the predictor survives it. Same family as the ascertainment caveat the occult-hypoxemia/AF work hit.
  Second meta-lesson (now three times): **stability ≠ validity** — the +0.067 was stable across 20 seeds; the
  mortality signal was cross-site consistent both directions; both were confounded. A stable/consistent effect still
  needs a confound/negative control before it's real. EEG program net after 3 outcomes: classifier me-too, mortality
  generic/WLST-confounded, seizure-prognosis ascertainment-confounded — the frozen foundation model never cleanly
  earned its keep on a clinical outcome in this data.

- **ComBat/CORAL harmonization does NOT remove EEG site/device leakage on spectral DSP features — and ComBat
  actively HARMS (bottleneck-remover #2 FAILED, 2026-07-10).** Tested the neuroimaging batch-effect removers on the
  IIC features (S0001 vs S0002, GPD/LPD vs slowing) hoping to kill the 0.71 site-probe while keeping cross-site class
  AUC. Result inverted the goal: a correct parametric-EB ComBat drove the site-probe from **0.708 → 0.999** (a tree
  recovers site PERFECTLY afterward) while degrading the biological class AUC **0.741 → 0.610**; CORAL (covariance
  alignment) also left site-tree at 0.999 (class 0.661). Diagnostic decomposition: (a) ComBat DID kill the *linear*
  site probe (0.674 → 0.273), so marginal mean/scale was removed; (b) but a *tree* still nails site — and it is NOT a
  degenerate-feature artifact (0 near-constant/var-ratio>1e3 features; variance ratios all ~0.5–2.3); (c) the site
  fingerprint is DISTRIBUTED over real slow-wave features (delta/alpha ratio, slow_ratio + their within-window std;
  50% of site-importance in 3 features, 90% in 11 of 48). MECHANISM: the two hospitals differ in the higher-order
  JOINT/interaction structure of slow-wave spectral features, which survives location, scale, AND covariance
  alignment; ComBat makes it WORSE because stripping the shared marginal physiology (what it's designed to equalize)
  removes the biological variation that was diluting the pure site-interaction fingerprint, sharpening it for a
  nonlinear probe. RULE 1: harmonization is the WRONG tool for EEG-DSP site leakage — never report cross-site EEG
  performance "after ComBat"; it can look clean marginally while a nonlinear model is fully site-confounded AND the
  biology has been attenuated. RULE 2 (methods-cautionary, publishable): any EEG-foundation-model paper claiming
  cross-site generalization after ComBat is suspect. RULE 3 (strategic): the fix for EEG confounding is NOT subtracting
  site — it is WITHIN-subject / WITHIN-device measurement-reclassification designs (deployed measure vs a ground-truth
  reference from the SAME monitor), which are confound-immune by construction. This test therefore CONFIRMS the pivot
  away from cross-site prediction toward the BIS-occult-suppression class of design.

- **A naive peak-to-peak amplitude threshold is NOT a burst-suppression detector — it conflates low-voltage EEG with
  isoelectric suppression (raw-EEG confirmation FAILED, 2026-07-10).** To independently confirm BIS occult
  suppression, tried to detect suppression directly from VitalDB's raw BIS-sensor waveform (EEG1_WAV, 128Hz, µV) via
  "peak-to-peak <5–15µV over 0.5s = suppressed." Built the validation gate FIRST (detector must reproduce the
  monitor's own SR): it FAILED — per-case corr(mean monitor SR, raw-detector supp) = **−0.386** (wrong sign); cases
  with monitor SR≈0% showed raw-detector "suppression" of 15–21%. MECHANISM: a fixed µV peak-to-peak threshold flags
  any quiet/low-gain stretch (small-amplitude fast activity, high electrode impedance, low montage gain) as
  suppression; true burst-suppression is near-ISOELECTRIC and the validated SR algorithm is gain/noise-floor
  normalized. Also range-check fired (raw waveform spanned ±1500µV = artifact-laden). RULE: never claim a home-built
  physiologic-event detector without validating it against the device's own validated output on easy cases FIRST; if
  it doesn't reproduce the reference, its downstream numbers are meaningless regardless of how clean they look. For
  suppression specifically, rest on the monitor's FDA-cleared SR — do not re-derive it from raw voltage with a naive
  threshold. Consequence for the BIS-occult-suppression finding: it must stand on the monitor's own SR (an internal
  BIS/SR inconsistency), NOT on a raw-EEG re-derivation — which weakens the "BIS misses real suppression" claim and
  caps its tier.

- **A measurement-reclassification finding needs an INDEPENDENT gold-standard reference — a reference from the SAME
  device is fatally circular (BIS occult-suppression KILLED for top tier, 2026-07-10).** Why C8 (cuff-misses-
  hypotension) WORKED and BIS-occult-suppression did NOT, despite identical template: C8's reference (arterial line)
  is a truly INDEPENDENT instrument from the deployed measure (cuff). BIS's "reference" (the monitor's SR) comes from
  the SAME monitor and is algorithmically COUPLED to BIS (BIS blends the burst-suppression ratio into its own output;
  Rampil 1998), and the two use staggered smoothing epochs (BIS ~15–30s vs SR ~63s). So "BIS 40-60 while SR>0" is
  expected engineering lag, not clinician-invisible pathology — a monitor-self-referential co-occurrence, not a
  discordance between independent instruments. Compounding kills (independent sonnet red-team): (a) the age gradient
  merely re-derives KNOWN age-dependent suppression susceptibility (Purdon, Fritz) — rediscovery, not discovery; (b)
  SR>0 is a near-zero threshold catching trivial isoelectric blips; (c) my independent raw-EEG confirmation FAILED
  (r=−0.386, wrong sign) so there is NO orthogonal check; (d) no delirium outcome in VitalDB; (e) ENGAGES (JAMA 2019)
  minimized suppression DIRECTLY and still found no delirium benefit — which UNDERMINES the proposed mechanism rather
  than supporting it. Tier ceiling = technical note (A&A/BJA/JCMC: "display SR alongside BIS"), NOT NEJM/JAMA. RULE:
  before running a measurement-reclassification study, confirm the reference is a physically/algorithmically
  INDEPENDENT instrument from the deployed measure; a same-device sub-parameter is not a gold standard. This is the
  single cleanest discriminator between C8 (won) and the EEG depth-monitor ideas (capped).

- **META-CONCLUSION of the EEG top-tier loop (2026-07-10): a NEJM/JAMA/Nature-tier EEG finding is NOT reachable with
  current compute + data access; the ceiling is gated, and the honest output is to name the gate.** The loop ran
  every reachable EEG angle and each capped at the same two root gates: (1) NO GPU → frozen foundation models
  (CBraMod) never cleanly beat 48 classical DSP features on any clinical outcome, so the model can't earn a top-tier
  claim; (2) NO external dataset with EEG + hard-outcome + a 2nd site → no NEDC key for TUH/TUSZ, VitalDB lacks
  delirium, HEEDB is site-confounded and harmonization CANNOT remove it (ComBat makes it worse). Angles tried & their
  ceilings: IIC binary classifier = me-too; IIC→mortality = generic encephalopathy severity (neg-control kill);
  seizure-prognosis = ascertainment/monitoring-intensity confound; BIS occult-suppression = circular/known-physiology
  technical-note; ComBat harmonization = fails (site leakage is higher-moment). The reachable EEG win is
  Anesthesiology/A&A-tier measurement notes. The genuine top-tier white space (first cross-site-validated EEG-
  foundation-model → clinical-outcome study) remains exactly where CLAUDE.md said it is: GPU-gated + credential-gated.
  Correct machine behavior = surface the gate to the user, not force a capped finding past the bar.

- **"EEG foundation models predict site not physiology" is REFUTED under class-balanced cross-site designs — site
  leakage is real but SEPARABLE from the clinical signal (confound-as-finding paper KILLED, 2026-07-10).** Tried to
  turn the session's site-leakage failures into a methods paper ("cross-site EEG clinical prediction is dominated by
  hospital identity"). Ran the definitive decomposition on the balanced IIC set (GPD/LPD vs slowing, class 50/50
  WITHIN each site, so site⊥class by construction): site-probe 0.71–0.78 BUT within-site class AUC ≈ cross-site
  (gap ≈ 0: CBraMod 0.719 vs 0.751; classical 0.741 vs 0.741); dropping the top-20 site-predictive features leaves
  class AUC essentially unchanged (0.750→0.749); corr(feature site-importance, feature class-importance) ≈ 0.05
  (CBraMod) / −0.19 (classical). MECHANISM: the site fingerprint and the IIC-class signal live in DIFFERENT feature
  directions, so once class prevalence is balanced across sites the class prediction is NOT confounded by site — it
  generalizes. The site confound only bites when the clinical LABEL correlates with site (unbalanced prevalence, e.g.
  the real seizure data: S0001 19% vs S0002 5%). RULE: site-separability (a high site-probe) does NOT by itself imply
  the clinical prediction is site-confounded — you must show the predictive features ARE the site-leaky ones (D3/D4
  ablation) AND that label⊥site is violated. This both KILLS the dramatic methods paper and VINDICATES cross-site EEG
  classification under balanced/matched designs (a positive, but a me-too task: CBraMod 0.75 ≈ classical 0.74).
  Net: the salvageable methods nugget shrinks to "ComBat is counterproductive AND unnecessary when class is balanced
  across sites" — a modest technical note, not Nature-tier.

- **eICU has a VALID measured co-oximetry SaO2 gold standard (VitalDB & INSPIRE do NOT) — occult-hypoxemia is
  reachable, and the reference-validity gate is a 5-min pH-correction test (2026-07-11).** Before building any
  pulse-ox occult-hypoxemia (SpO2 over-reads SaO2) study, GATE the SaO2 reference: is it MEASURED co-oximetry or
  CALCULATED from paO2? Decisive test = residual of SaO2 vs a pH/Bohr-corrected Severinghaus curve; if pH-correction
  collapses the SD toward ~0, SaO2 is a deterministic formula of (paO2,pH) = CALCULATED = INVALID reference.
  Results: **VitalDB `sao2` SD 1.68→0.31 after pH-correction = CALCULATED (INVALID, same failure as INSPIRE's
  gapped/calculated sao2).** **eICU `O2 Sat (%)` SD 2.50→2.03 = stays large = MEASURED co-oximetry (VALID).** Two
  corroborating tells for eICU: (a) measured Carboxyhemoglobin (n≈90k, med 1.0%) + Methemoglobin (n≈90k, med 0.4%)
  are present — these require a co-oximeter, so O2Sat is co-oximetry; (b) 735 distinct O2Sat values at 0.1 resolution
  + the occult-hypoxemia zone (SaO2 80–92%) fully populated (~31k readings) with NO gap (INSPIRE had a fatal 88–92
  gap). IMPLICATION: the occult-hypoxemia breakthrough (pulse-ox over-reads true SaO2 in low-perfusion states & by
  race; a unified noninvasive-monitoring failure with the C8 cuff-BP finding) is REACHABLE in eICU (measured SaO2 +
  race/ethnicity + vasopressors + mortality, all cached) and should be validated in MIMIC-IV as the 2nd site. RULE:
  apply this pH-correction gate to EVERY new SaO2 source before use — it has now decided 3 cohorts (INSPIRE ✗,
  VitalDB ✗, eICU ✓) cheaply. Note: local eICU lab.csv.gz is a partial download (gzip EOF) but still yields ~253k
  paired blood-gas draws — re-pull full file before the definitive run.

- **Hemodynamic occult-hypoxemia (novel bet) REFUTED; the pulse-ox study reduces to a rigorous Sjoding replication
  (2026-07-11).** Built the full eICU occult-hypoxemia pipeline on a VALID measured-co-oximetry reference (176,440
  ABG↔SpO2↔MAP paired readings, streamed from 146.7M vitalPeriodic rows without storing 35GB). VALIDATED: pulse-ox
  over-read bias is textbook-monotonic (SpO2−SaO2 = +0.2 at normal sat → +13.8 at SaO2 70–80); racial disparity
  replicates Sjoding NEJM 2020 (occult rate Black 12.6% vs White 5.3%, ~2.4×; RTM-safe miss rate Black 66% vs White
  50%); RTM-safe mortality consequence is real (at matched reassuring SpO2≥92, occult true-hypoxemia age-adj
  mortality OR 2.84 [2.61–3.09], patient-deduped). BUT the NOVEL angle that would make it top-tier — that LOW
  PERFUSION amplifies the over-read (unifying with the C8 cuff-in-low-flow finding) — is REFUTED: regressing bias ~
  SaO2level + MAP + pressor in the hypoxemic subset (n=10,221), the MAP coef is **+0.05 (z=+9), the WRONG SIGN**
  (bias slightly LOWER at low MAP), pressor null (z=1.6); bias-by-MAP-tertile within matched SaO2 bands confirms no
  amplification. MECHANISM for the null: true low-flow likely makes the pulse ox DROP OUT (no plethysmographic
  signal → no SpO2 value → excluded from pairing) rather than over-read — so the amplification, if it exists, is in
  SpO2 UNAVAILABILITY/quality (which eICU vitalPeriodic doesn't flag), not in the over-read of present readings.
  RULE: a physiologically-plausible mechanism (pulse ox needs pulsatile flow) is not evidence — test it directly at
  matched reference before betting a study on it; here the clean test killed it. Net: occult hypoxemia is well-trodden
  (Sjoding, Wong 2021, Fawzy 2022) and my differentiator failed, so this is a replication, not the breakthrough.
  The pipeline + validated eICU co-oximetry reference are now reusable assets for the next SaO2-anchored question.

- **Vitals-based severity anchors (MEWS/NEWS2) are NOT outcome-calibrated across race — anchoring triage-equity
  claims on them OVERSTATES "under-triage" (ED triage finding downgraded, 2026-07-11).** A two-center (Stanford
  MC-MED + MIMIC-IV-ED, ~500k visits) RTM-safe analysis showed Black/Hispanic patients get lower ESI acuity at
  matched objective vitals (NEWS2), robust to chief-complaint adjustment, a standardized anchor, all acuity cutpoints,
  and external replication — looked like a strong health-equity finding. The decisive DEATH-anchored validation
  (death is not biasable; admission is) KILLED the harm interpretation: at matched NEWS2, Black/Hispanic MORTALITY is
  markedly LOWER than White (NEWS2 5+: Hispanic ~5%, Black ~8% vs White ~11%) in BOTH cohorts → the vitals anchor
  over-states minority risk, so lower acuity is largely appropriate calibration, not bias. RULE: when a fairness/
  disparity finding conditions on an objective SEVERITY PROXY (vitals score, lab panel, risk model), you MUST verify
  the proxy is equally calibrated to a HARD, unbiasable outcome (death) across the groups — if minorities have lower
  death at matched proxy, the 'under-treatment relative to proxy' is partly proxy miscalibration, not discrimination.
  Admission/treatment endpoints are themselves biasable and cannot adjudicate this; death can. Meta: this is the 3rd
  promising lead this session dissolved by its own decisive validation (occult-hypoxemia hemodynamic, dyshemoglobin,
  triage) — the pattern is that a residual confound hides until the hardest-outcome test is run; run it EARLY.
  Residual real signals: Asian under-triage with EQUAL mortality (purer, small); Hispanic door-to-room +7min at
  matched acuity (operational). Salvage = a methods-cautionary paper, not a clinical-breakthrough claim.

- **The C8 arithmetic-attenuation template requires the deployed measure's error to be NOISE, not a specificity-
  increasing threshold shift — it does NOT transfer to SpO2/oxygenation (2026-07-11).** Redeployed the validated
  eICU SpO2<->SaO2 paired data (42,847 stays) into the exact C8 move: is the hypoxemia->mortality OR larger by GOLD
  SaO2 than by DEPLOYED SpO2 (as cuff attenuated hypotension-harm)? RESULT REVERSED: SpO2-defined OR is LARGER
  (SaO2<88 OR 3.27 vs SpO2<88 OR 6.14; ratio 0.53). MECHANISM: cuff error is ~random noise at low BP -> cuff flag is
  insensitive -> attenuated OR (C8). SpO2 error is a SYSTEMATIC over-read -> when SpO2 does cross <88 the patient is
  profoundly hypoxemic (true SaO2 even lower) -> the SpO2 flag is MORE SPECIFIC -> HIGHER OR. RULE: the C8
  "biased-measure attenuates the exposure-harm association" argument only holds when the measurement error is
  approximately non-differential NOISE around the truth; when the error is a monotone shift that makes threshold-
  crossing more specific for severity, the deployed measure can show a STRONGER (not attenuated) association -> the
  arithmetic-consequence reframe fails. Check the error structure (noise vs shift) before assuming attenuation. The
  only clean number was the KNOWN occult-hypoxemia point (SpO2 92-96 target permits 10-20% true SaO2<88; Sjoding).
  4th decisive-first kill this session; the discipline works (data in hand, one run, no wasted build).

- **VitalDB's 2-channel BIS *sensor* EEG cannot replicate subtle SPECTRAL anesthesia effects (age→frontal-alpha,
  Purdon-2015) even at n=249, though it captures GROSS phenomena (burst suppression, Ce→alpha dose-response) fine
  (2026-07).** Multitaper age→alpha main effect flat across absolute/relative/alpha-minus-slow metrics; but alpha
  rises correctly with propofol Ce (+2.26 dB/µg·mL⁻¹), proving the pipeline works. MECHANISM: research-grade
  age-alpha findings use full 10–20 montages with controlled impedance; VitalDB's proprietary frontal BIS sensor
  (2 ch, referential) attenuates the subtle spectral effect. RULE: match substrate quality to effect subtlety —
  gross-amplitude markers (burst suppression, spectral edge) survive limited montages; fine oscillatory/coherence/
  age markers need research EEG (→ HEEDB, not VitalDB). Validates anchoring spectral aims on HEEDB and using VitalDB
  only for the montage-robust burst-suppression validation.

- **A finding survives when its decisive disconfirming test is run and passes — Aim-3 (BS precedes hypotension)
  cleared the reverse-causation "fatal flaw" (2026-07, overnight).** Unlike the session's dissolved leads, the
  BS→hypotension result passed its make-or-break: the red-team's fatal concern (low BP flattens the 2-ch EEG →
  mislabeled BS → spurious "precedence") was refuted by restricting to currently-NORMOTENSIVE bins (MBP≥70): BS
  still predicts next-bin hypotension OR 4.98, and 4.25 with stable/rising MBP. Plus within-Ce-strata robustness
  (not dose) and a clean lead-lag structure (OR rises at +30..+120s). RULE CONFIRMED: run the decisive disconfirming
  test FIRST/EARLY; the ones that survive it (C8, this) are the keepers. Residual honest limits: Ce is effect-site-
  MODELED (not measured) → dose-timing confound; BS from a BIS sensor needs suppression-ratio/blinded validation;
  no outcome in VitalDB (→ HEEDB adds it). Tier: BJA/A&A methods-physiology; the OR-mechanism + ICU-outcome combo
  (VitalDB+HEEDB) is the path up.

- **Lag/precedence analyses must index on ABSOLUTE TIME, never on retained-row position — and the comparison set
  must be identical across arms (2026-07, caught at full-power rerun).** An interim n=174 analysis concluded that
  burst suppression had no relationship to heart rate (OR<1, symmetric) and that HR was therefore a clean internal
  negative control proving "vasomotor specificity." At n=1,852 this REVERSED: bradycardia is strongly associated
  with BS (OR≈4). Two bugs: (1) sequences were indexed positionally and then filtered by HR availability, so
  "lag −4" meant "4 retained bins earlier", not 120 s earlier — this manufactured negative-lag associations;
  (2) the HR-available subset is a selected subpopulation (tracks monitoring intensity) in which the hypotension
  asymmetry is genuinely weaker. After fixing to true 30 s time lags, the flagship precedence stands cleanly on all
  cases (negative lags 0.98/1.02/1.03 NULL; positive 1.50→1.71), and the real contrast is subtler and better:
  bradycardia is associated with BS but FLAT across lag (concurrent state, OR 3.8 before ≈ 4.4 after), whereas
  hypotension RISES with forward lag (temporal lead). RULE: when a striking dissociation appears in a subsample,
  re-derive it at full power with time-indexed lags and a fixed comparison set before it reaches a manuscript.
  Interim-sample dissociations are a classic artifact source.

- **A negative control that "works" is the alarm, not a curiosity — chasing a 5% discrepancy overturned two of
  three headline claims (2026-07, hardening pass).** Frontal EMG (same BIS sensor, NOT a measure of cortical
  suppression) was run as a negative-control exposure through the published two-phenotype model and came back
  OR 1.05 above baseline / 0.91 below — the same SIGN PATTERN as burst suppression, ~40x smaller. That should have
  been null. Following it produced three corrections:
  (1) **The two-phenotype dissociation was a difference-of-significance artifact.** "Significant above baseline,
      not significant below" rested on a stratum with 14x fewer bins (611,656 vs 44,006). Tested as a formal
      INTERACTION — ratio of the two Mantel-Haenszel ORs, both recomputed inside each case-level bootstrap
      replicate — it is 1.08 [0.89,1.32]. RETRACTED. The sevoflurane "external validation" replicated the
      significant/not-significant PATTERN, which any underpowered second stratum will do; it never replicated an
      interaction, because there was none.
  (2) **Bin-level CIs without case clustering are fiction.** ~600,000 bins from ~1,700 patients is n=1,700, not
      600,000. Every interval in the original draft was far too narrow.
  (3) **Scale changes masquerade as artifacts, and vice versa.** The drop from OR 2.06 to 1.18 looked like
      regression to the mean but was ~entirely a change of contrast: 2.06 is "per FULL suppression" while 1.18 is
      "any suppression vs none", and among suppressed bins the mean suppressed fraction is only 0.140. Isolating
      them on identical rows: binary+linear-MAP 1.20 vs binary+exact-2mmHg-strata 1.18 — the RTM artifact is real
      but small. The reporting SCALE was the bigger distortion. "Per full suppression" describes a contrast far
      more extreme than the phrase conveys to a reader.
  RULE, now mandatory for every bin-level analysis in this repo BEFORE anything is written up: (i) a
  negative-control exposure, (ii) EXACT stratification on any variable used to define the strata (a linear
  covariate does not remove regression to the mean when the strata are defined by that variable), (iii) case-level
  cluster bootstrap intervals, (iv) a backward-lag control, and (v) formal interaction tests — never compare
  significance across strata.

- **Self-controlled, dose-matched designs are the honest test of "independent of anesthetic dose" — and they
  change the answer (2026-07).** Adjusting for effect-site concentration as a linear covariate ACROSS patients
  does not support a dose-independence claim: deep anesthesia causes both suppression and vasodilation. Matching
  within (case x 4 mmHg current MAP x 0.5-unit dose) differences out every time-invariant patient characteristic
  by construction. Under that design the propofol association shrinks to OR 1.08 [1.03,1.12] at +120 s, with
  backward lags null (1.01-1.03) and a forward/backward asymmetry of 1.07 [1.02,1.12]. Small but real, and the
  EMG negative control goes cleanly null (0.95-1.00) under exact stratification — which is the positive evidence
  that the design is measuring physiology rather than the model.
  COROLLARY: dichotomizing a graded outcome wastes most of the signal. Re-asking the identical question with a
  CONTINUOUS outcome (signed dMAP in mmHg, case fixed effects) is far better powered and gives an interpretable
  effect size in mmHg instead of an OR on an exposure scale nobody can picture.

- **Range-check every physiological signal against physiological POSSIBILITY at load, before any modelling — the
  cluster bootstrap will not save you (2026-07, the largest error of the project).** `bridge_bins.csv` was never
  filtered: 4.27 % of MAP values were <= 0 (minimum **-78 mmHg**; negative arterial pressure does not exist) and
  0.62 % exceeded 200 mmHg. Unfiltered, dMAP spanned **-312 to +390 mmHg** and 2.5 % of bins showed >50 mmHg of
  change in two minutes. **Every reported number was inflated about threefold** (asymmetry -0.97 -> -0.33).
  HOW IT WAS CAUGHT, because the diagnostic generalises: two scripts disagreed (-0.971 vs -0.666) on row sets
  differing by **0.9 %**. An estimate that moves 31 % when you drop a fraction of a percent of the data is being
  driven by extremes. **RULE: any estimate materially sensitive to dropping a small fraction of rows is
  artefact-driven until proven otherwise.**
  AND THE PART THAT SHOULD FRIGHTEN US: the case-level cluster bootstrap did NOT catch it — its interval
  [-1.171,-0.763] EXCLUDED the value obtained from the slightly smaller sample. Cluster bootstrapping protects
  against CORRELATED observations, not CONTAMINATED ones. Filtering implausible VALUES is the principled fix;
  winsorising the outcome only masks them. Consolation: after filtering, the estimate was stable across four very
  different windows ([30,150],[25,160],[20,180],[40,140] -> -0.340,-0.330,-0.323,-0.333), which is what a real
  effect looks like and is a better result than the inflated one was.

- **A covariate that merely SHARES AN ENDPOINT with the outcome is nearly as bad as one that is collinear with it
  (2026-07).** Fixing an exact-collinearity trap (pre-trend = MAP(t)-MAP(t-k) is exactly -1x the backward outcome)
  introduced a PARTIAL one: MAP(t-k)-MAP(t-2k) shares the term MAP(t-k) with the backward outcome
  MAP(t-k)-MAP(t). Partial correlation 0.528 against the backward outcome vs 0.023 against the forward one. The
  damage was ONE-SIDED — it halved the backward coefficient (-0.412 -> -0.202) while leaving the forward one
  untouched (-1.278), inflating the headline asymmetry ~24 %. Fixed by moving the window to [t-3k, t-2k], which
  shares no endpoint with either outcome. RULE: for any lagged design, write out the algebra of which time points
  each covariate and each outcome contain, and require DISJOINT sets.

- **A negative control is not decoration — and one that is not null invalidates your significance criterion
  (2026-07).** Frontal EMG (same sensor, not cortical suppression) produced a SIGNIFICANT forward-minus-backward
  statistic under all three estimators (+0.19 to +0.57 mmHg; MH ratio 0.87 [0.81,0.94] significantly reversed).
  So "the bootstrap interval excludes zero" was NOT a calibrated decision rule for this design — it fired on an
  exposure that should be null. Fix: estimate exposure and control INSIDE THE SAME bootstrap replicate and report
  their DIFFERENCE. Subtlety worth keeping: the EMG bias was OPPOSITE in sign, so subtracting it made the result
  LARGER — a convenient correction, which deserves more scepticism than an inconvenient one, because EMG may
  carry real arousal physiology rather than pure design bias, in which case subtracting it OVER-corrects. Report
  raw AND contrast; treat the raw as the conservative bound on magnitude.

- **Translate the effect into the field's own outcome units BEFORE claiming impact — it can reverse the sign
  (2026-07).** A 0.33 mmHg asymmetry was translated into minutes below MAP 65, the metric the perioperative
  literature actually uses, expecting a small sustained displacement to move a threshold-crossing quantity. It did
  the opposite: population attributable fraction **-5.8 % [-11.5,-0.5]**, non-positive at every threshold from 55
  to 75 mmHg. This RECONCILES with the autoregulation stratification (asymmetry -0.678 at MAP>=90, null below 70):
  suppression lowers pressure FROM HIGH STARTING POINTS, where a sub-millimetre shift never crosses a clinical
  threshold. RULE: a mechanism can be real, specific, graded and blockable and STILL have no effect on the
  clinical endpoint. Check the endpoint translation before writing an impact claim, not after.

- **Use a NEGATIVE-CONTROL OUTCOME to test case-level associations — something the exposure cannot possibly cause
  (2026-07).** Cumulative suppression predicted AKI robustly (+3.44 pp/SD; +3.89 on an absolute-rise definition
  that never divides by baseline, so NOT a KDIGO denominator artefact). But it also "predicted" **pre-operative**
  creatinine (-0.226 mg/dL per SD), which is causally impossible — demonstrating residual patient-level
  confounding and reducing the claim to association. Related and equally instructive: suppression predicted MORE
  hypotensive minutes BETWEEN patients (+8.2 min/SD) and FEWER WITHIN patient (-0.98 min). Same data, opposite
  signs; the case-level "mediation" was measuring between-patient severity confounding and calling it a pathway.

- **Match the instrument's TIMESCALE to the physiology before interpreting a null (2026-07, a retraction).** I
  measured 30-second-averaged heart rate against 60-second pressure changes, got a slope of -0.0115 bpm/mmHg, and
  concluded the baroreflex was abolished under anaesthesia (~1 % of awake gain) — which conveniently explained why
  vasodilation moves pressure. The literature says gain is depressed 65-73 %, i.e. it RETAINS ~30 % (~0.22
  bpm/mmHg). My figure was ~20x low because the arterial baroreflex acts over ONE TO THREE HEARTBEATS and my
  window averaged it away. CLAIM RETRACTED. Same lesson for the HRV null: RMSSD is predominantly vagal and indexes
  CARDIAC autonomic control, so it cannot speak to VASOMOTOR sympathetic outflow — the right instrument is Mayer
  wave (~0.1 Hz) power in the arterial pressure signal.

- **Registered predictions are worth the embarrassment: six failed here and each one narrowed the mechanism
  (2026-07).** Failed: larger effect in the elderly (reversed), larger at higher dose (reversed), the transition
  rather than the state (refuted in both cohorts), suppression blunts baroreflex gain (null), suppression precedes
  an HRV fall (null), pressure overshoots after the episode (it decays to zero instead). Between them they
  excluded depth, cardiac, chronotropic, baroreflex and cardiac-autonomic mechanisms and left a vasodilatory one
  that survives. COROLLARY on derivation error: P1/P2 were registered as "more sympatholytic burden -> bigger
  effect" when the physiology says the effect scales with the tone REMAINING to be withdrawn — the derivation was
  wrong, not just the guess. Re-reading a failed prediction afterwards is worth nothing; the fix is to test the
  reinterpretation against a MEASURED moderator that did not exist when the hypothesis was formed.

- **A cohort defined BY an outcome cannot be used to measure that outcome's ascertainment — and the degenerate
  fit prints as a clean null (2026-07).** The HEEDB extraction cohort (16,244 patients) was deliberately defined
  as "EEG patient with an ascertained death", because every surviving test is ascertainment-immune and needs no
  survivors. Re-running the full battery against it produced two silent failures. (1) The ascertainment red-team
  reported a death-record rate of **100.0 % in every aetiology** — not a finding, the cohort definition read
  back; the real spread is 29.1-61.9 % and only exists in the unrestricted extraction. (2) The pre-specified
  primary, whose outcome is "a death record exists", fit an outcome that was identically 1 and printed
  `+0.00 pp [-0.00,+0.00] ns` for every coefficient — **visually indistinguishable from a genuine null result**,
  and briefly read as one. RULE: before interpreting any regression, check that the outcome varies; before
  interpreting any completeness or ascertainment statistic, check that its universe was not filtered on the very
  thing being measured. Both scripts now refuse rather than emit. The tell that something was wrong was not the
  statistics but an ARITHMETIC INCONSISTENCY between two runs of the same battery minutes apart (15,318 vs 3,302
  patients "with condition data") — the same tell that caught the unfiltered-arterial-pressure bug. Cross-run
  count reconciliation is the cheapest bug detector in this project and has now caught two of the worst errors.

- **A guard patch touched a variable the next test was reading (2026-07).** Fixing the above, I rebound `base` to
  the corrected CHECK 1 universe — but CHECK 2, forty lines below, iterated over `base` too. The result was a
  hybrid whose patient set came from one extraction and whose aetiology labels came from another, and it silently
  moved the analysable n from 3,216 to 3,078. Caught only because the n changed when nothing in CHECK 2 had been
  edited. RULE: when patching a shared-scope script, grep for every later use of any name you rebind, and treat
  an unexplained change in n as a bug until proven otherwise -- not as noise.

- **"Unexplained" in an EHR cohort usually means "not yet extracted" -- check extraction DEPTH, not just patient
  coverage (2026-07).** The headline limitation of the HEEDB study was that 45.7 % of burst-suppression patients
  had no aetiology label -- Brown's "challenging to determine" group, and the reason the finding looked fragile.
  It was an artefact. Two condition extractions both covered ~100 % of their target PATIENTS, but one held a
  median 168 codes per patient and the other 730 (4.3x). On the shallow one the unexplained fraction is 35-46 %;
  on the deep one it is 6.6 %, of which 91 % is epilepsy without status epilepticus and only 0.6 % of the cohort
  is genuinely unclassified. RULE: patient-level coverage ("99.9 % of the target list") says nothing about
  per-patient completeness, and a category defined by ABSENCE of a code is the one most corrupted by shallow
  extraction. Report rows-per-patient alongside patient coverage before treating any absence-defined group as
  real. COROLLARY: the same shallowness attenuates an ascertainment-differential toward the cohort mean, so the
  21.8 pp differential measured there is a lower bound -- which happened to be the conservative direction for the
  argument it supported, but that was luck, not design.

- **A registered prediction failed and the failure was more informative than the guess (2026-07).** Predicted:
  epilepsy-without-status suppression is pharmacological, so its 30-day mortality-timing coefficient should be
  NEGATIVE like status epilepticus (-7.48 pp) and unlike anoxic injury (+29.45 pp). Actual: +2.13 pp
  [-3.81,+8.09], null and positive-signed -- falsified by the pre-stated criterion. The error was equating
  "pharmacological" with "benign". A pharmacological cause predicts that suppression carries NO information about
  the brain, i.e. a coefficient of ZERO, which is exactly what was observed; it does not predict a protective
  signal. Status epilepticus's negative coefficient must therefore come from something else (plausibly that those
  patients are actively treated and survive the acute window), not from its suppression being drug-induced.
  RULE: when a mechanism predicts "this marker means nothing here", the registered prediction should be a NULL,
  and the analysis should be powered to say so -- not a signed effect borrowed from a superficially similar group.

- **The negative control did its job by FAILING, and that is the most useful thing that happened (2026-07).**
  H2 re-test: among burst-suppression patients who all died, exposure to a BS-capable anaesthetic (propofol,
  barbiturate, high-dose midazolam) within 24 h of the EEG was predicted to give a NEGATIVE 30-day timing
  coefficient -- suppression a drug explains should occur in brains that are not dying. Actual: **+31.00 pp
  [+27.50,+34.67]**, a large effect in the OPPOSITE direction, and the pre-specified negative control
  (dexmedetomidine, which sedates but does not produce suppression) was ALSO non-null at **-8.13 pp
  [-12.70,-3.55]** where a null was predicted. Read together the two are diagnostic: peri-EEG propofol marks an
  intubated, actively-resuscitated patient and dexmedetomidine marks one stable enough to be lightly sedated and
  weaned. The exposure was measuring ILLNESS SEVERITY, not drug-caused suppression. Corroborating detail: the
  anoxic coefficient fell from +29.45 to +20.46 pp when bs_drug entered the model, i.e. the drug term absorbed
  severity that aetiology had been carrying. RULE: a drug-exposure variable in an ICU cohort is a severity proxy
  by default and must be shown otherwise before it is read as pharmacology. Had the negative control been
  omitted, +31 pp was large, clean and significant enough to have been written up as a finding.
  DIRECT CONSEQUENCE for the recovery-of-consciousness study (docs/research/40_ROC_PIVOT.md): the same
  confounding applies there with the same sign, which is why that design commits in advance to conditioning on
  sedative dose and to restricting on the REASON sedation stopped.

- **"The immune analysis gives a BIGGER number, so the bias was diluting" is not a valid inference (2026-07).**
  Written into a findings document and caught only by an adversarial re-read: the ascertainment-immune design
  gave a 36.80 pp spread against the compromised primary's 22.96 pp, and I concluded differential ascertainment
  had been diluting rather than creating the effect. The two analyses estimate DIFFERENT ESTIMANDS on DIFFERENT
  COHORTS -- "was a death ever recorded" across all patients, versus "did death come within 30 days" among
  decedents only -- so their magnitudes are not commensurable and their difference says nothing about the
  direction of the bias. Worse, the same section already contained the opposite claim (that the bias
  "manufactures a spread ... in precisely the observed direction"), so the document asserted both directions four
  sentences apart. RULE: a bias-corrected estimate and a biased estimate are comparable only when they target the
  same quantity; if the fix changed the estimand, the change in magnitude is uninterpretable. The demotion
  argument never needed it -- an outcome whose recording completeness varies by exposure group is invalid in
  principle, which the ascertainment table establishes on its own.

- **Reporting two intervals and noting one is larger is the same shortcut, wearing a different hat (2026-07).**
  The specificity claim -- interaction spread 38.51 pp [32.84,44.63] versus aetiology main effect 12.13 pp
  [8.44,15.84], "3.2x, therefore specific to burst suppression" -- compared two separately-bootstrapped
  quantities without ever testing their difference, in a document that criticises exactly that shortcut two
  sections later for the cross-site comparison. Non-overlapping intervals are evidence but are not the test. The
  fix was nearly free because both spreads were already computed from the SAME resample index on every replicate,
  so differencing them per replicate gives a paired bootstrap directly. RULE: whenever a claim has the form "A is
  bigger than B", the reported statistic must be A-B with its own interval -- and check whether the existing
  bootstrap is already paired before assuming a new one is needed.

- **An imported helper silently redefined the cohort, and the result LOOKED like a clean falsification
  (2026-07).** The dose-response test imported eeg_times() from heedb_bs_ascertainment to map patient -> EEG
  time. That function skips reports whose `bs` field is empty, because it was written for the burst-suppression
  cohort -- so it returns times ONLY for BS-labelled patients. The dose-response model was therefore fit inside
  the BS-positive group, with the BS-negative comparison group silently absent, which makes its burden x
  aetiology interaction non-comparable to the label-based interaction it was built to reproduce. It duly came
  out with the wrong sign pattern and the script printed "D1 FALSIFIED" -- a confident, specific, wrong
  conclusion that would have gone into the paper as evidence against its own central claim.
  The tell was a distribution, not a coefficient: median burden in the analysable set was 0.439, when the
  measured median across all patients is 0.053 and BS-NEGATIVE patients sit at 0.013. A median 8x the
  population value means the cohort is not the cohort you think it is. RULE: after any join or filter, print
  the exposure's distribution and the size of each comparison group, and compare them against the same
  quantities computed on the full data -- a silently-restricted cohort shows up there long before it shows up
  in a coefficient. COROLLARY: importing a helper is not free of assumptions. The lesson "import the validated
  function, do not reimplement it" is right, but the imported function carries the cohort definition of the
  script it was written for, and that definition must be checked against the new use.

- **WebFetch on PubMed silently FABRICATES paper content when the site serves a CAPTCHA (2026-07). Treat every
  WebFetch-derived citation as unverified.** PubMed now returns "Checking your browser - reCAPTCHA" to automated
  fetches. WebFetch's summarizer did not surface the block: it returned confident, plausible, WRONG paper
  content, and returned DIFFERENT fabrications on repeated calls to the same PMID. This is the single most
  dangerous failure mode encountered in this project, because a fabricated quote from a real person's paper is
  exactly the error that destroys credibility, and it arrives looking like a clean result.
  RULE: bibliographic facts (title, authors, journal, volume/pages, abstract text) come from the NCBI E-utilities
  API, never from WebFetch:
      curl "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=<PMID>&rettype=medline&retmode=text"
  Full-text quotes come from PMC (pmc.ncbi.nlm.nih.gov/articles/PMC<id>/), grepped for the literal sentence.
  Everything load-bearing in this project has now been re-verified this way: the Guay/Brown review really is
  Anesthesiology 2025;143(6):1595-1618 with those six authors (PMID 41537509), the Safavynia abstract and its
  "warrant investigation of alternative determinants of delayed RoC" sentence are genuine (PMID 42294965), and
  Westover MB really is author 11 with Brown EN author 12.

- **Never pair two independently-ordered lists and assume the order matches (2026-07).** I built a PMID-to-title
  map by taking PMIDs from the PubMed MCP search tool and titles from a separate WebFetch of the search results
  page, both "sorted by date", and assuming row N of one was row N of the other. Six of nine were wrong -- a
  burst-suppression/delirium paper was actually a gamma-stimulation Alzheimer's trial, a nociception paper was
  actually a mouse DBS study. A subagent then wasted most of a run chasing the wrong papers before catching it.
  RULE: a citation is a single record fetched by ID, not a join between two lists that happen to be the same
  length. If two sources must be combined, join on a key present in both, never on position.

- **A falsification criterion that only tests DIRECTION will pass on a trivial effect (2026-07).** The
  reversibility mechanism test registered M3 as "conditioning on persistence SHRINKS the aetiology interaction
  ... FALSIFIED IF the paired difference covers zero". It passed: attenuation +2.70 pp [+1.57,+4.93], excluding
  zero. But the spread went 30.80 -> 28.09 pp, so persistence explains **8.8 %** of the thing it was proposed to
  explain, and 91 % of the aetiology interaction survives untouched. The prose said "attenuate SUBSTANTIALLY";
  the operational criterion said "excludes zero". At n=1,812 those are not the same test, and only the second
  one was written into the code. RULE: when a prediction is about a mechanism EXPLAINING something, the
  falsification threshold must be stated as a fraction of the effect to be explained (e.g. "fails unless it
  absorbs >= 50 % of the spread"), never as significance of the attenuation. Significance answers "is there any
  attenuation at all", which is not the question a mechanism claim asks.
  SUBSTANTIVE RESULT, worth keeping: reversibility is REAL but SMALL. Anoxic suppression is +16.25 pp more
  likely to persist [+12.65,+19.59], and persistence independently predicts 30-day death at +22.94 pp
  [+16.79,+28.94] from a landmark where every patient was alive when persistence was measured. So "repeat the
  EEG" carries genuine prognostic information over and above the diagnosis. It is simply not what the aetiology
  interaction is made of. Next candidate: burst MORPHOLOGY -- post-anoxic bursts are stereotyped ("identical
  bursts") where drug-induced bursts are variable, and that is measurable on raw EDF already being read.

- **Test whether the finding is CLINICAL BEHAVIOUR before hunting biological mechanism (2026-07).** Two
  mechanism tests were run (depth: ruled out; reversibility: 8.8 %) before anyone asked whether the aetiology
  interaction needed biology at all. It partly does not. After cardiac arrest, burst suppression is a guideline
  criterion for poor prognosis and drives WITHDRAWAL OF LIFE-SUSTAINING THERAPY; in sepsis it does not. The
  pathway is demonstrably present in these data: anoxic BS+ patients die at a median of 5 days versus 189 days
  for anoxic BS-, and the BS x aetiology interaction computed on ACQUIRING A DNR/PALLIATIVE CODE is 22.80 pp, so
  the EEG is changing decisions and not only outcomes. Landmarking past the withdrawal window (day-7 survivors)
  retains 17.00 pp [11.34,24.13] of a 37.54 pp interaction -- about HALF. So the effect is neither artefact nor
  clean biology, and the landmark figure is the one that should be quoted. RULE: for any prognostic marker that
  is ALSO used to make treatment-limitation decisions, self-fulfilling prophecy is a first-order threat, not a
  discussion-section caveat, and it must be tested before mechanism work is commissioned. The cheap decisive
  tests are the timing distribution, a care-limitation code as an alternative OUTCOME, and a landmark past the
  decision window. All three ran in one pass on data already extracted.
  COROLLARY on ordering: three competing threats (coexisting EEG findings 96 % retained, ceiling artefact not
  applicable, age/sex 101 % retained) were cleared in the same run at negligible cost. Cheap threat-elimination
  should precede expensive mechanism extraction as a matter of course -- the morphology extraction was already
  running when this was ordered, which is the wrong sequence.

- **An interaction coefficient is NOT the effect within a stratum, and I wrote a paper's headline claim as though
  it were (2026-07).** The document said burst suppression "carries little weight" in sepsis and is "close to
  uninformative", on the strength of a sepsis interaction coefficient of -14.92 pp. Computed WITHIN sepsis, the
  effect of burst suppression on 30-day death is **+17.9 pp** (50.6 % vs 32.7 %) -- large by any standard. The
  coefficient was negative only RELATIVE TO A REFERENCE GROUP; the stratum effect is main effect plus
  interaction, and every aetiology came out strongly positive (+17.9 to +38.3 pp). The whole "in sepsis it is
  benign, plausibly because it reflects sedation" story was an artefact of reading a contrast as a level, and it
  had survived a red-team, a literature check and several rewrites.
  RULE: whenever an interaction is interpreted substantively, PRINT THE STRATUM-SPECIFIC EFFECTS -- unadjusted
  cell means and their differences -- next to the coefficients. Two minutes of arithmetic on raw cells would
  have caught this at any point. It surfaced only because a Kaplan-Meier analysis parameterised the same
  question as within-stratum differences and the numbers disagreed with the prose.
  SUBSTANTIVE CONSEQUENCE: the finding narrows from "suppression means opposite things in different diseases" to
  "suppression is roughly twice as lethal after anoxia as in sepsis". Still real, still worth reporting, much
  less dramatic -- and the claim that this explains CONTRADICTORY literature weakens to explaining inconsistent
  MAGNITUDES, since no aetiology shows a null or reversed effect.

- **A bias test can return "no effect" because the proxy is blunt, not because the bias is absent (2026-07).**
  Censoring follow-up at the first dated DNR/palliative code -- the method Elmer 2023 recommends for
  self-fulfilling-prophecy bias -- moved the interaction from 20.41 to 20.64 pp, i.e. not at all. Reported
  naively that is strong evidence against withdrawal bias. It is not: acute withdrawal is followed by death
  within hours, and in these data the median gap from code to death is 42 days with only 5 % dying within a day.
  The codes document chronic care-limitation status, not acute post-arrest withdrawal, so the test cannot see
  the thing it was aimed at. RULE: before reporting a null from a bias-correction, verify the proxy behaves like
  the mechanism -- here, a simple histogram of proxy-to-outcome timing showed it does not. A null from a blunt
  instrument is inconclusive, not reassuring.

- **The dosimeter test: right about the ordering, wrong about the sign, and the unpredicted pattern was the
  finding (2026-07).** Hypothesis: burden indexes INJURY after anoxia and SEDATION DEPTH elsewhere. P2 confirmed
  -- the burden->death slope is steeper in anoxic than sepsis (+12.43 pp [+5.90,+19.32]) or metabolic (+6.72
  [+1.19,+12.98]). P1 FALSIFIED -- I predicted the anoxic slope would be steeper WITHOUT peri-EEG anaesthetic
  (pure injury signal, undiluted); it was shallower, -7.77 pp [-18.54,+3.84].
  The unpredicted pattern is the informative part. In EVERY aetiology the burden slope is far steeper in patients
  WITH peri-EEG anaesthetic: sepsis 12.11 -> 37.80, metabolic 16.60 -> 41.30, structural 10.45 -> 33.77, status
  12.14 -> 57.02 (2.5x to 4.7x). ANOXIC IS THE EXCEPTION, at 32.70 -> 40.47, only 1.24x, because burden already
  predicts death in unsedated anoxic patients where in every other aetiology it barely does (10-16 pp/unit).
  So a version of the hypothesis survives, inverted from the one registered: burden is informative WITHOUT a drug
  only after anoxia, and elsewhere it is informative mainly WHEN a drug is on board -- i.e. elsewhere it measures
  "this cortex suppressed at a given dose", a SENSITIVITY signal, not an injury one. My P1 reasoning was about
  dilution when it should have been about what the unsedated stratum means.
  RULE: when a prediction fails, check whether the ordering it implied still holds before discarding the
  hypothesis -- and read the stratum the prediction ignored, which here carried the result.
  CAVEAT that blocks over-reading: peri-EEG anaesthetic is a severity proxy in this cohort (H2 failed exactly
  that way), so the sedated/unsedated split is confounded and this is a lead, not a conclusion.

- **The "anoxic patients are just sicker" rival is dead (2026-07).** It predicts baseline severity and effect
  size should track together. Across aetiologies r = +0.350, weak. Decisively, anoxic and sepsis have essentially
  IDENTICAL BS-negative 30-day mortality -- 32.8 % vs 32.7 % -- while their burst-suppression effects differ
  almost twofold (+38.3 vs +17.9 pp). Equal baselines cannot generate unequal effects through severity alone.
  Cheap, decisive, and it should have been run before any mechanism work.

- **The two-fold gap is REAL: it survives a blinded quantitative definition and the withdrawal window (2026-07).**
  Two gating tests, either of which could have reframed the whole finding, both came back in its favour.
  LABEL NOISE, REFUTED. The worry was that "burst suppression" is applied strictly in post-arrest EEGs (where
  prognostication protocols demand it) and loosely in sepsis, packing the septic BS+ group with milder patterns.
  Discarding the clinician label entirely and defining suppression as measured burden above a fixed,
  aetiology-blind threshold reproduces the gap at every threshold: anoxic:sepsis ratio 2.04 by label, and 2.00,
  2.02, 1.99, 1.89 at burden thresholds 0.02-0.20. It only compresses at 0.50 (1.42) where n collapses.
  WITHDRAWAL, REFUTED AS AN EXPLANATION OF THE GAP -- though not as an inflator of the absolute effect. Among
  day-7 survivors every aetiology roughly halves (anoxic 38.30 -> 18.40 pp, sepsis 17.89 -> 8.47) but the RATIO
  is untouched: 2.14 -> 2.17. So early death and withdrawal inflate every aetiology proportionally and do NOT
  make anoxia special. This is the distinction the earlier pooled landmark could not make, because a pooled
  interaction spread conflates "the effects are bigger" with "the effects differ more".
  RULE: when a confounder is suspected of creating a DIFFERENCE between groups, test the RATIO or the contrast,
  not the levels. A confounder that scales everything equally is a nuisance, not an explanation.

- **The "independent prognostic axis" claim for burst morphology was wrong, and I had flagged the reason in
  advance (2026-07).** Morphology alone gave AUC 0.671 and I described it to the user as an independent
  prognostic axis. Burden was not in that model. Burst duration -- the strongest apparent predictor at
  -12.09 pp/SD -- correlates **r = -0.745** with suppression burden, because shorter bursts mechanically mean a
  more suppressed record. With burden included, four of five morphology features go non-significant (only burst
  AMPLITUDE survives, +3.56 pp/SD) and the incremental AUC over aetiology+age+sex+burden is **+0.008
  [+0.004,+0.021]** -- an interval excluding zero and an effect of no consequence. The registered expectation
  that G1 would bite hardest was correct, which is the only reason this was caught before it was written up.
  RULE: before calling any derived feature an INDEPENDENT axis, put the obvious parent variable in the model and
  report the incremental discrimination, not the standalone figure. And state the effect-size threshold in
  advance: a significance-only criterion passed here on a +0.008 AUC, exactly as it did on an 8.8 % attenuation
  in the reversibility test.

- **Burst suppression is not merely the top rung of a steeper ladder -- the unification FAILED, and that is a
  stronger result than success would have been (2026-07).** Hypothesis: burst suppression and generalized
  slowing are two rungs of one severity ladder (none / slowing / discharges / suppression), and the ladder is
  simply steeper after anoxia. Three registered tests, three informative outcomes.
  L1 PARTIALLY FAILED. Rungs 1->2->3 are cleanly monotone in ALL FIVE aetiologies (anoxic 31.4 -> 32.0 -> 71.1;
  sepsis 31.5 -> 34.9 -> 50.6; metabolic 26.6 -> 31.1 -> 55.8; structural 24.0 -> 29.0 -> 47.1; status
  16.7 -> 22.6 -> 43.4), which validates the assumed ordering of discharges above slowing. But RUNG 0 misbehaves:
  post-anoxic patients with NO malignant finding die at 43.3 % against 31.4 % for those with slowing (n=150).
  A clean EEG after arrest should not be worse than a slow one; that stratum is small and probably heterogeneous
  (technically limited records, deaths from cardiac rather than neurological causes) and needs its own look.
  L2 FALSIFIED as specified, because I chose the wrong span. The 0->3 span difference was +4.25 pp
  [-4.55,+12.76], covering zero -- but it inherits the broken rung 0. Measured 1->3, i.e. suppressed versus
  merely slow, the contrast is +39.7 pp in anoxic against +19.1 pp in sepsis, a clean twofold difference that
  reproduces the headline. RULE: when a composite statistic covers zero, check whether one component is
  contaminated before concluding the effect is absent.
  L3 FALSIFIED DECISIVELY, and this is the substantive finding. Conditioning on ladder position did not absorb
  the burst-suppression gap; it INCREASED it, from +20.41 to +23.43 pp (absorbed -14.8 %). Compared against the
  ADJACENT malignant rung rather than against everything below it, suppression's aetiology gap is larger, not
  smaller. So burst suppression is not "the top of a ladder that is steeper after anoxia" -- it is specifically
  different from the categories immediately beside it.

- **The gap is EEG-specific, but every predictor behaves somewhat differently across the two populations
  (2026-07).** The negative controls passed: burst suppression's anoxic-minus-septic difference of +20.41 pp
  exceeds age (-6.62), heart failure (-8.31), malignancy (-9.51), dementia (-9.91) and chronic kidney disease
  (-10.14), each tested by paired bootstrap against burst suppression inside the same resample. But note that
  all five controls are NON-ZERO and all negative, so chronic-illness markers systematically predict LATER death
  in anoxic than in septic patients -- plausibly because post-anoxic early death is dominated by acute brain
  injury, so chronic morbidity selects the subgroup not dying that way. The right claim is therefore that burst
  suppression's gap is roughly TWICE the largest non-EEG predictor's and opposite in sign, not that non-EEG
  predictors show no gap at all.

- **The ladder is not novel; the aetiology-dependent SLOPE of it is. Two canonical scales already exist, one per
  aetiology, and nobody has compared them (2026-07).** An adversarial literature check found the ordinal severity
  ladder is long-established and partly guideline-endorsed, so presenting it as new would have been the kind of
  error a knowledgeable reviewer names in one sentence. Verified verbatim from MEDLINE records:
    * WESTHALL 2016, Neurology, PMID 26865516 (TTM trial, n=103 post-arrest): EEGs classified "into highly
      malignant (suppression, suppression with periodic discharges, burst-suppression), malignant (periodic or
      rhythmic patterns, pathological or nonreactive background), and benign EEG (absence of malignant
      features)"; 37 % highly malignant, all with poor outcome, specificity 100 %. This is our rung ordering,
      already published, and now embedded in ERC-ESICM prognostication guidance -- for CARDIAC ARREST ONLY.
    * YOUNG 1992, J Clin Neurophysiol, PMID 1552002 (n=62 with positive blood cultures): EEGs classified "into
      five groups: normal, excessive theta, predominant delta, triphasic waves, and suppression or burst
      suppression, IN ASCENDING ORDER OF SEVERITY", which "correlated with percent mortality, even within a
      single clinical group". An ordinal severity ladder built and mortality-validated in SEPSIS ONLY.
    * SYNEK 1988, PMID 3416501: a five-grade coma scale, "generally applicable only to coma after diffuse brain
      trauma and cerebral hypoxia" -- again single-aetiology by the author's own statement.
  So the field has TWO ladders, built separately in the two aetiologies we are comparing, at n=103 and n=62, and
  has never put them side by side. THE NOVEL CLAIM IS THE COMPARISON, not the ladder: the same severity ordering
  has a materially different slope after anoxia than in sepsis. That is a sharper and far more defensible
  statement than "burst suppression means different things", and it comes with its own ancestry to cite.
  ALSO NOTED: Westhall groups suppression AND burst-suppression together in one "highly malignant" tier, which
  is a published prior on the V3 question of whether attenuation ranks above burst suppression -- their answer is
  that it does not, they are equivalent. Any result separating them is a claim against that grouping.
  CAUTION recorded: Lamartine Monteiro 2016 (PMID 26567031) found periodic discharges superimposed on a mildly
  slow background carried 100 % poor outcome, i.e. as bad as burst suppression, so collapsing "periodic
  discharges or seizures" into one rung below suppression is a simplification a careful reviewer can attack.

- **The posterior-dominant-rhythm modifier was reverse causation, and the pre-registered confound test caught it
  (2026-07).** Scoring both flags as "present on ANY report", a preserved posterior rhythm appeared to collapse
  the burst-suppression effect in every aetiology -- sepsis +22.80 -> +5.58, status +37.64 -> +4.93, anoxic
  +37.12 -> +21.37 -- with a mechanism that predicted the direction (intact thalamocortical machinery means
  suppression is a state, not a property of the tissue). It was largely an artefact: a patient suppressed on day
  1 who recovers a rhythm on day 6 counts as rhythm-present, so the contrast partly compared patients who
  RECOVERED against those who did not.
  Scoring both flags on the INDEX recording, the modification falls to +0.13 (anoxic), +3.30 (sepsis), +7.20
  (metabolic), +5.07 (structural), +11.91 (status) -- significant in 2 of 5 and an order of magnitude smaller.
  Among SINGLE-REPORT patients, where reverse causation is impossible by construction, it is significant in 0 of
  4. The claim is withdrawn; at most a small residual survives in metabolic and status.
  RULE: any "modifier" built from longitudinal flags must be scored on the SAME observation as the exposure, and
  the single-observation subset is the cleanest test because the confound cannot exist there. The registered
  expectation -- that attenuation was expected and the claim survives only if substantial modification remained
  -- is what made this a clean withdrawal rather than a negotiation.

- **"Conditioning on severity increases the gap" was arithmetic, not biology (2026-07).** I read the
  burst-suppression gap rising from +20.41 (vs all lower rungs) to +23.43 (vs the adjacent rung) as evidence
  that suppression is specifically different from the categories beside it. An adversarial brainstorm pointed out
  the simpler reading: the pooled reference INCLUDES the slowing rung, and slowing carries an equal-and-opposite
  aetiology gap (-20.76), so pooling partially cancels the burst-suppression gap and restricting to the adjacent
  rung (gap +2.64, near zero) merely removes the cancellation. RULE: before interpreting a change in an effect
  when the REFERENCE CATEGORY changes, compute what the reference's own aetiology gap contributes -- a shift in
  the comparator can move an estimate without anything about the exposure changing at all.

- **RASS cannot measure sedation in a study of burst suppression -- the instrument is circular (2026-07).** To
  test whether septic suppression is drug-induced I used the RASS score nearest the EEG as a sedation-depth
  measure. RASS grades RESPONSIVENESS, and burst suppression CAUSES unresponsiveness, so "RASS <= -4" is partly
  the exposure itself. Two symptoms showed it: post-anoxic burst-suppression patients scored MORE deeply sedated
  (82.8 % at RASS <= -4) than septic ones (61.1 %), the reverse of the drug-dilution prediction; and restricting
  to RASS > -4 collapsed EVERY aetiology's effect by about 80 % (anoxic +34.53 -> +6.32), because it selects the
  peculiar subgroup labelled burst-suppressed while remaining arousable. Both results are uninterpretable.
  The right instrument was available all along: drug_sedatives carries drug_exposure_END_datetime as well as
  start, so an infusion can be tested for being ACTIVE at the recording -- a measure of the drug rather than of
  the patient's response to it, which the EEG finding cannot cause. RULE: when the outcome, exposure or
  covariate is a level of consciousness, any consciousness-derived covariate is suspect; prefer a measure of what
  was DONE to the patient over a measure of how the patient RESPONDED.

- **Mode of death differs sharply, and it is a SHAPE difference not a location one (2026-07).** Among
  burst-suppression patients who died, 46.3 % of post-anoxic deaths fell within 96 h against 21.1 % of septic
  ones, a difference of +25.19 pp [+21.53,+28.68] (medians 5 vs 28 days). Anoxic death after suppression is a
  fast, clustered event; septic death is attrition spread across weeks. This was tested as a concentration
  fraction precisely because a median shift alone does not discriminate the mechanisms -- a uniformly earlier
  distribution and a front-loaded one have different implications and the same median ordering.

- **The sign pattern is scale-robust (2026-07).** Every gap in this project is a difference of proportions, and
  such differences can behave differently from odds ratios even away from floors and ceilings. On the log-odds
  scale the pattern is unchanged: burst suppression +0.872 anoxic-minus-septic, generalized slowing -0.957,
  GPDs +0.094 -- same signs and same ordering as the percentage-point versions (+20.41, -20.33, +2.64). Also,
  the burst-suppression gap is stable across reference categories (+20.41 against all lower rungs, +21.10
  against the adjacent rung, +21.31 against slowing alone), so the earlier worry that the comparator choice was
  driving it is resolved: it was noise between two cohort definitions, not composition.

- **Drug-induced suppression does NOT explain the septic dilution -- mechanism B is dead (2026-07).** Three
  registered predictions, all falsified, using a proper instrument (an infusion ACTIVE at the recording, from
  drug start and end datetimes) after RASS proved circular.
  I1 FALSIFIED and instructively: an infusion was running at the EEG in 74.3 % of post-anoxic burst-suppression
  patients against 64.0 % of septic ones -- the REVERSE of the prediction. The assumption that post-arrest
  protocols wean sedation before prognostication is simply wrong in this database, where post-arrest EEGs are
  frequently recorded during targeted temperature management with sedation running. That is worth knowing
  independently of this test.
  I2 FALSIFIED: the burst-suppression effect was LARGER with a drug running in 5 of 5 aetiologies, not smaller.
  I3 FALSIFIED: restricting to patients with no active infusion narrowed the anoxic-septic gap by 16.8 %
  [-1.75,+8.29], below the registered 30 % threshold and covering zero.
  So the gap is not drug dilution. Combined with the earlier eliminations, the surviving account is that WHAT
  PATIENTS DIE OF differs by aetiology. RULE, reinforced: an assumption about clinical PROTOCOL ("sedation is
  weaned before prognostication") is an empirical claim about the data and should be measured before a mechanism
  is built on it -- here it was false, and measuring it took one query.

- **The gap is NOT a timing artefact: the log-odds gap is FLAT from 7 days to a year (2026-07).** This is the
  strongest positive result in the project and it was obtained by a test designed to kill the surviving
  mechanism. If the aetiology gap existed only because post-anoxic death is front-loaded, then lengthening the
  horizon lets septic patients accumulate their deaths and the gap must compress -- in a cohort where everyone
  eventually dies it must approach zero by construction. The percentage-point gap does exactly that: 21.10 (7 d),
  20.41 (30 d), 18.13 (90 d), 16.77 (180 d), 13.32 (365 d), declining monotonically as predicted.
  But on the LOG-ODDS scale, which is not mechanically compressed as rates approach one, the gap is flat:
  +0.736, +0.872, +0.849, +0.844, +0.732. The 30-to-180-day decline is 3.2 % [-11.6,+17.9] against a registered
  40 % threshold. So burst suppression after anoxia confers roughly the SAME RELATIVE excess risk at every
  horizon out to a year. Post-anoxic patients with suppression are not merely dying sooner; they are more likely
  to die, and front-loading explains the absolute compression while explaining none of the relative effect.
  RULE, now demonstrated twice: report both scales. A percentage-point difference and an odds ratio answer
  different questions, and here they give opposite impressions of whether the effect decays.

- **Label overlap was DILUTING the gap, not inflating it -- it doubles in single-aetiology patients (2026-07).**
  Restricting to patients carrying exactly ONE of the five aetiologies moves the anoxic-versus-septic gap from
  +20.41 to +42.16 pp, a 107 % change on n=4,568. The expectation was the opposite -- that dual-coded patients
  would inflate a spurious contrast -- so this is a falsified prior in the favourable direction: patients coded
  as both anoxic AND septic blur the comparison, and removing them sharpens it. CAUTION before this is used:
  single-aetiology patients are a selected group (fewer comorbidities, cleaner presentations, shorter admissions
  accumulating fewer codes) and the doubling may partly reflect that selection rather than a purer contrast. The
  headline should stay with the full-cohort figure and report the restriction as a sensitivity analysis, not
  the other way round.
  Also confirmed in the same run: the gap appears at BOTH hospitals separately (+17.47 pp at S0001, +24.72 at
  S0002), and it does not depend on how soon after the arrest the EEG was recorded (+26.08 within a day, +35.95
  at 1-3 days, +30.22 beyond three days).

- **A FLAT CUMULATIVE ODDS RATIO IS WHAT A FIXED EARLY MASS PRODUCES -- I read it as a persistent hazard and
  was wrong (2026-07).** The marginal log-odds gap was flat from 7 days to a year (+0.736, +0.872, +0.849,
  +0.844, +0.732) and I concluded the excess was not a timing phenomenon: "these patients are not merely dying
  sooner, they are more likely to die". The landmark analysis refutes that. Conditioning on survival:
      day 0  -> 30 d window   gap +0.832 [+0.650,+0.990]
      day 30 -> 30 d window   gap +0.217 [-0.097,+0.544]
      day 90 -> 90 d window   gap +0.251 [-0.096,+0.569]
      day 180-> 180 d window  gap -0.206 [-0.552,+0.129]
  Among patients who survive 30 days there is NO aetiology-specific excess. The gap is exhausted.
  THE ARITHMETIC I MISSED: a cumulative measure ("death BY time T from the EEG") keeps counting the doomed
  compartment's day-2 deaths in every later numerator, so a fixed early mass produces an approximately CONSTANT
  cumulative odds ratio. Flatness of a cumulative OR is therefore evidence about nothing -- it is compatible with
  a persistent hazard AND with a fate sealed on day one. Only conditioning on survival distinguishes them.
  RULE: to ask whether a hazard persists, condition on being alive at a landmark and measure forward. Never infer
  persistence from the shape of a cumulative curve measured from a fixed origin.
  THE SHAPE CONFIRMS IT: anoxic BS+ patients die 40.6 % within three days against 12.5 % of anoxic BS-, and
  18.8 % survive past 180 days against 51.0 % -- a distinct early mass plus an unremarkable remainder, which is
  the mixture signature and not a proportional shift.
  CONSEQUENCE: the finding narrows and sharpens. Post-anoxic burst suppression identifies a subgroup whose fate
  is largely determined at the recording; among month-one survivors it carries no aetiology-specific information
  at all. That is more clinically actionable than "twice as lethal", and it is also a much more falsifiable claim.
  IT ALSO KILLED TWO CANDIDATES BEFORE THEY COST ANYTHING: global ischaemic dose causing multi-organ injury, and
  permanent disability generating complications, both predict a PERSISTENT hazard and are refuted by the same
  result.

- **Asked the right question, the "inert" morphology features work -- +0.038 cross-validated (2026-07).** The
  same five burst-morphology features that explained 1.4 % of the aetiology gap and added +0.008 AUC over burden
  when asked to explain the CROSS-AETIOLOGY contrast, add **+0.038 cross-validated AUC** when asked which
  post-anoxic burst-suppression patients die within three days (burden alone 0.632 -> burden + morphology 0.670,
  n=660), above the +0.02 threshold registered in advance. The features were never inert; the question was wrong.
  RULE: before discarding a measurement as unpredictive, check that it was asked a question it could answer. A
  feature that fails as a MEDIATOR of a group difference can still work as a DISCRIMINATOR within a group, and
  those are different jobs.
  The picture is coherent and every term is a named quantity: within post-anoxic suppression, three-day death is
  predicted by high burden (0.746 vs 0.386 between the two outcome extremes), high intra-burst 8-30 Hz content
  (+9.72 pp/SD; 0.250 vs 0.120), SHORT bursts (-7.55 pp/SD; 1.84 s vs 2.87 s), and the ABSENCE of generalized
  slowing (29.7 % in those dead by three days against 74.9 % in those alive past six months) and of a posterior
  dominant rhythm (12.3 % vs 24.3 %). Cross-validated AUC 0.697 for burden + age + findings; cross-hospital
  0.755 and 0.680. Burden alone shows no optimism at all (in-sample 0.676, cross-validated 0.677).
  NOTE the slowing result: having slowing ALONGSIDE suppression is strongly favourable, which is the same
  mirror-image fact seen earlier at cohort level (slowing's aetiology gap was -20.76 against suppression's
  +20.41), now reappearing as a within-patient discriminator.

- **Persistence works when landmarked properly (2026-07).** Among post-anoxic burst-suppression patients alive
  at a follow-up recording, suppression that PERSISTED carried 76.8 % 30-day death against 41.8 % where it had
  resolved (+34.9 pp; 82.1 % vs 49.0 % at 90 days). It could not be used for the three-day outcome at all,
  because a patient must survive to have a second recording -- using it there would have manufactured a powerful
  predictor out of immortal time. Only 98 patients resolved, so the estimate is imprecise, but the design is
  sound.

- **Quantitative burden stratifies inside a guideline category treated as homogeneous -- the clinically usable
  result (2026-07).** Westhall's "highly malignant" tier (suppression, suppression with periodic discharges,
  burst-suppression), now in ERC-ESICM guidance, is categorical: every patient in it formally carries the same
  information. Within it, measured suppression burden stratifies three-day death 24.7 / 26.4 / 34.2 / 49.6 /
  66.4 % across quintiles (monotone) and thirty-day death 52.3 % to 93.1 %. Adding burden to the category
  improves cross-validated AUC from 0.648 [0.616,0.676] to 0.741 [0.703,0.790], an increment of +0.093 against a
  registered +0.03 threshold, replicating cross-hospital at 0.719 and 0.678, with no in-sample optimism
  (0.684 vs 0.682). Morphology adds a further +0.036.
  WHY THIS IS THE RESULT AND THE AETIOLOGY COMPARISON WAS THE ROUTE: the aetiology gap turned out to be a fixed
  subgroup effect exhausted by day 30, which is interesting but not actionable. Asking which patients are in
  that subgroup produced something a clinician could in principle use, and it addresses a stated limitation of
  current guidance rather than a curiosity.
  THE CAVEAT IS NOT OPTIONAL AND IS WRITTEN INTO THE DOCUMENT: burst suppression already informs withdrawal of
  life-sustaining therapy, 40.6 % of these patients die within three days, and this cohort cannot separate
  biological from withdrawal-mediated death in that window. A risk score inside a category used to justify
  withdrawal could make its own predictions come true. The result is a statement about information present in
  the recording, not a recommendation to act on it.

- **Suppression burden is a BRAIN-SPECIFIC dosimeter, not a proxy for whole-body ischaemic dose (2026-07).**
  Cardiac arrest damages kidney, liver and myocardium alongside cortex, so burden might have been a marker of
  total ischaemic dose with the EEG as its most visible display. Three lines of evidence say no.
  (a) Acute kidney injury runs BACKWARDS against burden in post-anoxic patients, -16.08 pp per unit
  [-23.80,-7.79], where the global-dose account requires it to rise.
  (b) The gradients that ARE positive are not anoxia-specific: cardiac injury +12.54 pp per unit in anoxic
  against +27.73 in SEPSIS, and vasopressor exposure +18.55 against +24.60. Steeper in the aetiology with no
  global ischaemic event, so they mark severity generally rather than ischaemic dose.
  (c) Conditioning on kidney, hepatic and cardiac injury absorbs 2.6 % of burden's effect on three-day death
  (attenuation +0.99 pp [-1.75,+3.40]) against a 25 % threshold registered in advance.
  CAVEAT THAT LIMITS (a) AND (c), and it is a real one: 66.4 % of the highest-burden patients die within three
  days, and organ-injury CODES TAKE TIME TO ACCRUE. So the negative AKI slope is plausibly survivorship rather
  than biology, and the mediation null cannot fully separate "organ injury is not the pathway" from "there was
  no time for organ injury". The SPECIFICITY failure in (b) is the cleaner evidence, because it does not depend
  on follow-up time.
  RULE, general: when an outcome is a diagnosis CODE and the exposure predicts early death, the code is
  competing with death for the chance to be recorded. Any null or reversed association between them must be
  checked against time-at-risk before it is read as biology.

- **The clinical consequence is worth stating: this belongs in neuroprognostication and nowhere else.** If
  burden had been a whole-body dose marker, a suppressed EEG after arrest would also have been a statement about
  the kidneys, and the appropriate response would have been systemic. It is not. The EEG is reporting on the
  organ that determines the outcome.

---

## 2026-07-26 — the vasopressor withdrawal instrument, retracted before it was reported

- **A result was produced, looked strong, and was thrown away.** `heedb_wlst_pressor.py` reported that 74.1 % of
  post-anoxic burst-suppression patients dying within three days died within six hours of their last vasopressor
  ending, with a matching 81.4 % "pressor running at death". Taken at face value that is a decisive withdrawal
  signature and it would have changed what the main result *is*. It is an artefact.

- **The tell was a number that was the same everywhere.** The median gap from last pressor to death was **0.0 h**
  in every group: anoxic, septic, metabolic, structural, with and without burst suppression. Withdrawal practice
  is not identical across those aetiologies — burst suppression is a withdrawal criterion after arrest and is not
  one in sepsis — so a marker that cannot tell them apart is not measuring the decision.
  RULE, general: **when a putative clinical marker takes the same value in groups whose clinical handling is
  known to differ, suspect the data-generating process before believing the marker.** Uniformity across strata
  that should differ is evidence *against* validity, not for robustness.

- **The direct check settled it in one table.** `heedb_pressor_charting_check.py` histogrammed the interval:
  20.9 % exactly tied to the death timestamp, **0 patients** between 1 minute and 1 hour, 4 between 1 and 6 hours,
  and 64.1 % more than a week out (median 100 days — a previous admission). No clinical or biological process
  produces a spike at exactly zero with a literal void beside it. An open infusion is closed out at the recorded
  time of death.

- **The two "independent" columns were one event.** "Ended within 6 h before death" and "start ≤ death ≤ end"
  are both satisfied by an exposure whose end is stamped AT the death time. They agreed because they were the
  same indicator, which is exactly why their agreement felt confirmatory.
  RULE, general: **before reading two measures as corroborating each other, check whether one row of data can
  satisfy both definitions simultaneously.** Interval endpoints that coincide with the outcome time make
  "during" and "just before" the same set.

- **Diagnose the instrument on the raw distribution, not on the summary.** The summary table (fractions ≤6 h,
  ≤24 h, median) was compatible with the true story and with the artefact. Only the binned interval histogram
  separated them, and it needed no EEG, no S3 and about a minute of compute. That check should have run *before*
  the analysis, not after it.

- **What this does and does not cost.** It costs an answer, not a result. The main finding is unchanged: the
  caveat in `42_MAIN_RESULT.md` §4 already said this cohort cannot separate biological from withdrawal-mediated
  death inside the three-day window, and that caveat now rests on a documented failed attempt rather than an
  assertion. Answering it needs a source that timestamps the **decision** — a comfort-care order with an
  activation time, a ventilator-termination event, a documented family meeting — none of which exist here.

- **Third instrument to fail on the same question.** DNR/palliative codes failed (median 42 days from code to
  death — chronic status, not an acute decision); sedation-based proxies failed (circular: burst suppression
  causes unresponsiveness); vasopressor timing fails (charting). The pattern is that **administrative tables
  record states and billing events, not decisions**, and a decision-time question asked of them will keep
  returning the shape of the record-keeping.

---

## 2026-07-26 — the audit that mattered more than the experiment: look-ahead in the headline exposure

Context: S3 credentials were absent, so no new data could be touched. The session was spent auditing every
number in `42_MAIN_RESULT.md` against the raw log that produced it. Every reported figure transcribed
correctly — and the audit still found the most serious problem in the project, because **transcription was
never the risk; the definition was.**

- **Reconciling two logs found it.** Two scripts reported the same nominal cohort — "post-anoxic
  burst-suppression patients" — as 1,410 with 40.6 % three-day death and 1,405 with 43.4 %. Chasing a 2.8 pp
  discrepancy nobody had reported led to the cohort-construction code, where the real defect was.
  RULE, general: **when two scripts compute the same quantity, diff their numbers even if only one is
  published.** The unpublished one is a free replicate, and disagreement localises to a definition.

- **The defect.** `heedb_vs_guideline.py` starts the outcome clock at the patient's earliest recording, but took
  burden as `max` over ALL recordings, the Westhall category as an `or` over ALL reports, and morphology from
  whichever CSV row was read last. Survivors accrue more recordings than people who die on day two, so the
  exposure window was partly a function of the outcome. Measured exposure: **41.0 % of patients** have their
  maximum from a later recording, 21.8 % differ by >0.10 burden, mean burden 0.244 → 0.148 index-only.

- **Sign the bias before panicking about it.** Only survivors can accrue extra recordings, so the contamination
  raises burden among people who LIVED — it works against the observed gradient. The effect's existence is safe;
  its magnitude and its description as a bedside-prediction AUC are not.
  RULE, general: **a look-ahead finding is not automatically fatal. Work out which way it pushes.** A
  conservative bias leaves the qualitative claim standing and bounds the quantitative one.

- **Three separate loaders had the same bug in three different disguises** — `max()`, `or`, and last-write-wins.
  It was invisible because each looked like ordinary defensive aggregation.
  RULE, general: **any per-patient aggregation over repeated measurements is a look-ahead until proven
  otherwise.** In a survival analysis the number of measurements is itself an outcome. Ask of every `max`,
  `any`, `or` and bare assignment over rows: *could a later row have changed this, and could the patient's fate
  have changed whether that row exists?*

- **The check cost nothing and should have run first.** `heedb_burden_lookahead_check.py` needs no S3, no model
  and about a second of compute: count measurements per patient, compare max to index. That is a
  ten-line question that should be asked of every repeated-measures exposure BEFORE the headline analysis, not
  after it has been written up.

- **On the value of a no-data session.** Being unable to run anything forced re-reading what had already been
  run. That produced a more consequential result than the experiment it replaced. When an instrument is
  unavailable, audit — do not idle, and do not invent an analysis to fill the time.

- **The same bug was in 17 scripts, and the worst instance inverted the safety argument.** After finding
  look-ahead in the headline burden, a sweep found the pattern everywhere: `max` over recordings, `or` over
  reports, last-write-wins morphology. For burden the bias is conservative. For
  `heedb_landmark_class.py` it is NOT: one "suppressed ever" flag reused at every landmark means late-labelled
  patients — survivors by construction — dilute the exposed group at late landmarks, making the excess look more
  exhausted than it is, which is the direction of the reported Class A conclusion.
  RULE, general: **sign the bias separately for every analysis the pattern touches.** "The bias is conservative"
  was established for one estimand and does not transfer. A shared bug does not have a shared direction.

- **A landmark design's whole purpose is that the exposure was known at the landmark.** Collapsing a
  repeated measurement to one per-patient flag silently discards that guarantee while the code still looks like
  a landmark analysis. Keep the per-recording pairs and re-evaluate the exposure at each landmark.

- **Delegate the enumeration, verify the classification.** haiku's sweep of 20 files was accurate on all five
  claims checked against source — including the two it labelled *lower* risk, which is where an error would
  have been most costly to miss. Spot-check the lower-risk calls, not just the alarming ones: a false alarm
  costs an hour, a missed one ships.

- **A 403 that looks like expired credentials can be a credential-precedence collision.** A session began with
  the bootstrap hook announcing "BDSP_AWS_* not set — HEEDB access unavailable", and every S3 call returned 403.
  Both were true and the conclusion drawn from them was wrong: working keys were sitting in `~/.aws/credentials`
  from an earlier session, and the 403 came from the container's *placeholder* `AWS_ACCESS_KEY_ID` /
  `AWS_SECRET_ACCESS_KEY` (agent-proxy stubs), which **outrank profile credentials in boto3's resolution
  chain**. Every script authenticated as the stub.
  The diagnostic that settles it in one call is `sts get-caller-identity` **per credential source**: the stub
  returns `InvalidClientTokenId`, a real key returns an ARN. `head_object` alone cannot distinguish "bad
  credentials" from "no permission on this object".
  RULE, general: **before concluding an access problem is expiry or permissions, enumerate which credential
  source is actually being used.** Env vars beating a profile is silent, and the failure mode is indistinguishable
  from expiry at the call site.

- **Fail-closed messages must probe, not infer.** The hook inferred unavailability from an unset variable rather
  than testing the thing it was reporting on, and its message was then believed for a whole session. It now
  probes `~/.aws` before announcing anything. Any bootstrap that reports capability should test the capability.

- **The corrected re-run: the finding survived, and one of two predictions was wrong.** Burden measured at the
  index recording still stratifies three-day death inside the highly-malignant category (29.5 % → 73.1 %,
  monotone), the increment over the guideline falls +0.093 → **+0.068** but stays above twice the registered
  +0.03, and cross-hospital replication becomes *more* symmetric (0.679 / 0.669 vs 0.719 / 0.678). The
  look-ahead was inflating the headline number, not manufacturing the finding — which is what signing the bias
  had predicted.
  The landmark prediction was **wrong**. Correcting the exposure was supposed to weaken Class A; it slightly
  strengthened it (−37 % of the day-0 gap vs −25 %). The 17–21 % misclassification was real — the script now
  prints it, 382 of 1,827 patients at the 0-day landmark exposed by their own future — and simply did not
  operate the way the mechanism said it would.
  RULE, general: **sign the bias, then still measure it.** Signing is what tells you whether the finding is
  worth re-running for; it is not a substitute for the re-run. One of the two signs here was right and one was
  wrong, and there was no way to know which from the argument alone.

- **Always keep a switch that reproduces the old behaviour, and check it digit for digit.** `BURDEN_SCOPE=max`
  reproduced the legacy log exactly — every quintile, AUC, CI and cross-hospital figure. That control is what
  makes "the increment fell from +0.093 to +0.068" a statement about the exposure definition rather than about
  some unnoticed refactor that came along for the ride. A corrected number with no reproduction of the
  uncorrected one is not a comparison.

- **A result that moves under a fixed bias and survives is worth more than one never checked.** The audit trail
  is kept in the main document rather than deleted, because the correction is part of the evidence.

- **A registered threshold does not protect you if the statistic can be produced without the mechanism.** The
  trajectory analysis pre-registered "change adds ≥+0.03 CV AUC over level ⇒ reversible". It returned +0.064 and
  printed CONFIRMED. But `level + change` is algebraically `first level + second level`, and a second
  measurement beats one whenever the measure is noisy — so the registered statistic was satisfiable by
  measurement error alone. Pre-registration disciplines *when* you decide, not *whether the statistic means what
  you think*.
  RULE, general: **before registering a threshold, ask what else could produce the number.** If a
  no-biology mechanism can clear the bar, the test needs a control that the mechanism cannot pass — here, the
  increment as a function of the INTERVAL, which reversibility must grow with and noise cannot.

- **Check the interval distribution before interpreting any "change over time" analysis.** The median gap
  between a patient's first two EEGs was **0.65 days** and only 57 of 701 pairs were ≥2 days apart. The whole
  structural-vs-reversible framing assumed days. Repeat EEGs in an ICU cohort are mostly same-admission
  re-reads, which is a fact about clinical practice that silently redefines what "trajectory" means.

- **Regression to the mean reproduces "improving beats worsening" with no recovery in the causal chain.** A
  first reading high by noise appears to improve on remeasurement and also carries a lower true value, so those
  patients do better. Any within-level change analysis on a noisy measure will show this. It is not evidence of
  reversibility and must be named whenever a change score is stratified by baseline.

- **Stratify change analyses by baseline, then distrust the result anyway.** Unstratified, the table was
  incoherent — improvers died more often than stable patients, contradicting the analysis one section above it.
  That incoherence was the tell that the strata differed in baseline rather than in trajectory. An internal
  contradiction between two sections of the same output is a debugging signal, not noise to reconcile in prose.

- **Predictive increment cannot identify a mechanism when the measure is noisy.** Four framings of
  structural-vs-reversible all produced positive increments (+0.062, +0.063, +0.037) and all were satisfiable
  with no biology: two noisy readings of a CONSTANT quantity beat one reading. The identifying move was to stop
  asking "does adding this improve prediction" and re-express the pair as orthogonal contrasts —
  `mean = (first+last)/2` and `diff = last−first` — then test the SIGN of the difference term. Noise cannot
  give a correctly-signed non-zero coefficient on the difference; only real change can.
  RULE, general: **when two measurements of the same thing are available, decompose into mean and difference
  before interpreting either.** Increment tests conflate "better estimate of a level" with "information about
  change"; the decomposition separates them by construction.

- **The best evidence in that whole analysis required no model at all.** If a marker tracks a CHANGING state,
  the most recent reading is the best one. If it estimates a FIXED quantity with error, the AVERAGE of two
  readings beats the most recent. Average 0.787 vs most-recent 0.747 settles it in one comparison, with nothing
  fitted to the trajectory. Look for the version of the question that is a direct observation before building
  a model of it.

- **Three confounds, three redesigns, opposite conclusion.** The first run printed "CONFIRMED (reversible)";
  the answer is structural. The intermediate stages were not wasted — each one named a specific confound
  (algebraic identity, cohort selection, recency, noise-averaging) and the final design had to survive all four.
  A result that flips under redesign is not a reason to distrust the process; failing to redesign is.

- **`procedure_occurrence` in a claims-derived OMOP instance is a BILLING table, not a record of what was done.**
  It contains intubation, tracheostomy, ECMO and CPR — all separately reimbursed — and contains no extubation
  and no comfort care, because neither generates a bill. The reasoning that led there was sound ("an extubation
  is an act with a timestamp, unlike a drug end-time") and the premise was wrong.
  RULE, general: **before choosing an administrative table as an instrument, ask what makes a row appear in it.**
  Billing tables see reimbursable acts; state tables see charted statuses; neither sees decisions. A clinical
  event that is important but unbilled is systematically invisible.

- **Check that a concept_id column is actually populated before building on it.** `observation_concept_id` is
  100 % zero in this instance — every row unmapped — and the source values are `General`, `Note`,
  `marital_status`. An extraction filtered on that column returns an empty file that is indistinguishable from
  "this never happened". One `Counter` over 100k rows would have shown it in seconds, and should be the first
  thing run against any table before it is designed around.

- **Four instruments, one root cause, and naming it is the result.** DNR codes (chronic state), sedation depth
  (circular), vasopressor end-times (charting artefact) and procedures (unbilled) all failed the same
  underlying way: administrative data records what is billed or what is charted as a state, and withdrawal of
  life-sustaining therapy is neither. A caveat backed by four identified failure mechanisms is stronger than an
  unexamined caveat, and is itself reportable — "this cannot be determined here, and here is precisely why" is
  a finding, not an absence of one.

- **Check the disease before trusting a mechanism argued from first principles.** "Dead cortex cannot seize, so
  structural loss predicts fewer later seizures" is sound physiology and wrong here: post-anoxic status
  epilepticus arises in SEVERELY injured brains and is seen in almost a third of comatose arrest survivors
  (De Stefano, J Neurol 2023, PMID 36076090). Severe hypoxic-ischaemic injury is itself epileptogenic, so both
  competing hypotheses predicted the same sign and the test discriminated nothing.
  RULE, general: **a mechanistic prediction is only as good as its premise about the specific disease. Run the
  literature check BEFORE the analysis, not after it.** One E-utilities query would have killed this design in
  minutes; instead it cost a full build-and-run cycle.

- **When a fix makes the effect stronger, the diagnosis was wrong.** The positive association was attributed to
  GPD/LPD overlapping the burst-suppression pattern, so the outcome was narrowed to seizure and status alone.
  The association nearly doubled (+12.9 to +22.3 pp). That is a refutation of the explanation, not a
  refinement of it, and it should be read that way rather than absorbed as noise.

- **Do not "fix" a confound by conditioning on a post-exposure variable.** Restricting to patients no longer
  suppressed at the later recording flips the estimate's sign. That restriction conditions on a collider --
  a variable caused by the exposure -- and can manufacture exactly such a reversal. A sign flip between two
  arms of the same test is a signal that the design, not the biology, is doing the work.

- **Bound what is established, separately from what is desired.** Q3 has a real answer from two independent
  lines -- burden is brain-specific, and behaves like a fixed quantity measured with error -- and does NOT have
  a positive tissue-level identification, because all three external references failed for three different
  reasons. Reporting the first without the second would be the overclaim.

- **A validity figure living in a code comment is not a validity figure.** The exposure underpinning every
  quantitative claim in this project carried "the calibration that achieved AUC 0.829" in a comment, with no
  reproducible analysis behind it. Measured properly it is 0.749 — real agreement, overstated by 0.08.
  RULE, general: **any number that justifies a measurement must exist as a runnable analysis, not as prose.**
  Comments are not evidence and do not get re-checked when the pipeline changes.

- **Switching from a linear probability model to logistic made the effect BIGGER (+0.068 to +0.100).** The
  convenient-but-wrong model was the conservative one here. Do not assume methodological shortcuts flatter the
  result; check, because "we used the crude method and still found it" is a much stronger sentence than the
  alternative and it is sometimes true.

- **Discrimination without calibration is half a result, and the missing half is the half clinicians use.** AUC
  says the ranking is right; calibration says the risk is right. Reporting an intercept of -0.013 and a slope of
  0.980 alongside the AUC costs one extra analysis and answers the first question any statistician asks.

- **Know your reader's own literature before claiming novelty.** This project spent its whole life on burst
  suppression without citing the group that built the standard estimator for it and proposed the mechanism.
  Once read, the central result reframed itself from a statistical curiosity into an extension of an existing
  model -- a better result, reached by reading rather than by computing.

- **A measure taken in a different *place* is not a different *thing*.** Predicted 0.60 that the whole-record
  background would beat the intra-burst measure, on the reasoning that slow activity lives between bursts and
  our measure looked only inside them. Falsified: mutually redundant. Predicted 0.45 that topography would add,
  on the reasoning that every feature we compute takes a median across channels and a human reader does not.
  Falsified: out-of-bag increment +0.014 [-0.021, +0.040] over burden + background + intra-burst. Two
  over-predictions, one error: **spatial or temporal separation of two measurements is not evidence that they
  load on different factors.** What would be evidence is a case where one moves and the other does not.

- **Test the necessary condition when the sufficient one is out of reach, and take the negative seriously.**
  The clinician's slowing flag lives in HEEDB; I-CARE has no equivalent, so no I-CARE analysis can show that
  topography explains the flag residual. It can show whether spatial information carries outcome signal the
  non-spatial measures do not -- which the hypothesis *requires*. That failed, so the hypothesis fails with it.
  A negative on a necessary condition is decisive in a way a positive never is.

- **Smoke-test an analysis on PERMUTED labels rather than real ones.** It exercises every code path -- joins,
  missing columns, degenerate subgroups, plotting -- on real feature distributions while revealing nothing
  about the association, so the registration stays clean. It also does something a normal smoke test cannot:
  run it a few hundred times and it becomes a direct measurement of the false-positive rate. Doing exactly
  this surfaced a 95 % interval excluding zero on data with no signal, which is how the calibration audit of
  `diff_ci` and `oob_increment` came to be run at all.

- **A mask that compresses out bad samples silently glues time together.** Dropping dead-channel frames and
  then binning what remains is correct for any order-free summary and wrong for anything that models
  transitions. One recording in 24 had a 1,817 s hole closed up, which a state-space estimator reads as an
  abrupt jump that never happened. The defect was invisible in the output -- burden was unaffected and every
  number looked plausible. It was found by reading the extraction code, not its results.

- **Deriving an exclusion is half the work; checking whether it is outcome-related is the other half.**
  Excluding the 73 glued recordings removes patients at 75.3 % poor outcome versus 61.2 % retained,
  -14.1 pp [-24.6, -2.9]. The same shape as the burst-morphology exclusion. Neither exclusion was chosen with
  outcome in view and both are related to it, because sicker patients produce worse recordings -- which means
  the check has to be run every time rather than reasoned about.

- **A measure that differs in KIND survives where measures that differ only in LOCATION did not.** Three
  candidates for the clinician-flag residual were tested the same way. The whole-record background spectrum
  and the spatial topography were each predicted to add and each turned out redundant; the across-days trend
  in burden was predicted *not* to add and did (+1.061 [+0.233, +2.057] adjusted for burden, background and
  intra-burst content). The first two differed from what we already had only in *where* they were measured.
  The third differs in *what kind of thing* it is — a rate of change rather than a level. That distinction is
  now the first thing to ask of any new candidate, and it is worth more than a plausibility argument.

- **Test the sign, not the increment, whenever a decomposition could gain accuracy by averaging noise.** Both
  trend arms confirmed on the coefficient's sign while **every** out-of-bag increment included zero. Had the
  increment been the test, a real and correctly-directed association would have been recorded as nothing. Had
  the increment been the *headline*, a finding with no discrimination gain would have been oversold. Reporting
  both, and declaring in advance which one decides, is what keeps those two errors from trading places.

- **When selecting on "has a second measurement", find out who is missing before interpreting anything.**
  Patients with a usable late recording are 56.5 % poor against 74.1 % among those without, −17.6 pp
  [−25.5, −9.1]. A late recording exists only for someone who lived to be recorded, so the estimand silently
  became "the trend among patients who survived to be measured twice" — a real question, but not the one the
  hypothesis was about, and the sickest patients are outside it.

- **Check that the two things you are differencing are actually two things.** The cached burden files record
  the ACTUAL hour of the recording nearest each target, not the target. Patients with few recordings get the
  same file for several targets, so 15.4 % of h12/h24 "pairs" were one recording differenced against itself —
  a change of exactly zero by construction. Left in, they would have diluted a real effect toward the null and
  produced a negative result indistinguishable from biology. One line of counting found it.

- **The summary you take from an estimator can matter more than the estimator.** On real EEG the causal BSP
  filter *averaged over a window* scores 0.3146 at 300 s; the same filter *read at the window's last bin*
  scores 0.5738 and loses to a crude threshold ratio. The instantaneous estimate is the thing BSP uniquely
  provides, and it is the worst predictor of an interval — a value near 0 or 1 at one bin cannot represent
  five minutes containing both states. The first version of that analysis reported only the point estimate and
  would have understated the method badly. When an estimator can be summarised more than one way, report both;
  the gap between them is a finding, not a nuisance.

- **A more elaborate estimator does not extract more from a fixed sample — it uses a larger one.** Given
  exactly the same data as a threshold ratio, BSP was never more accurate at any window length, and got worse
  as windows shortened (1.007 to 1.087). Everything it gains at short windows it gains from data outside them.
  This is the third time this project has predicted that sophistication would beat simplicity on identical
  inputs and been wrong; the useful question is not "is the model better" but "does it get to see more".

- **Bracket a claim with two baselines, not one.** Asking whether BSP beats exponential smoothing has no
  single answer: it beats a causally-tuned EWMA in simulation at every window, loses to an oracle-tuned one
  everywhere, and on real EEG loses to the tuned one at 1–2 s. One baseline would have licensed either "the
  state-space model earns its keep" or "three lines of arithmetic suffice", both defensible and both
  incomplete. Two baselines that bound the answer from opposite sides say what is actually true.

- **Near-perfect agreement between two instruments is a reason to run a negative control, not to celebrate.**
  The report-text slowing flag agreed with MORGOTH's expert annotation in 99.8 % of overlapping patients. That
  is not achievable between genuinely independent reads of a subjective EEG feature, and it was not what it
  looked like: patients annotated for *focal* slowing were also 99.8 % generalized-slowing-flagged. The number
  measured the population, not the concordance. The control cost one extra query and reversed the conclusion.

- **Ask what makes a row appear in an annotation corpus before joining to it.** MORGOTH's GENSLOWING set is
  positives-only — assembled to train a detector, not to survey a cohort — so absence from it carries no
  information at all. The same question applied to a billing table once cost this project an instrument;
  applied here it saved one.

- **A linear adjustment cannot absorb a step, and the leftover looks exactly like signal.** The slowing flag's
  positivity is flat to 10 % suppression burden and then collapses (92.7 % to 56.1 %). Adjusting for burden
  linearly therefore leaves the non-linear part of that relationship in the residual — a mechanism for the
  project's biggest open constraint that requires no biology. Whenever an adjustment variable and an exposure
  are related non-monotonically, check the functional form before interpreting what survives it.

- **When a replication fails its own gate, the downstream verdict is not "negative" — it is absent.** The
  flexible-adjustment test printed "the residual COLLAPSES" on a cohort where the baseline residual had never
  reproduced. Both readings were unsupported. Analysis scripts should refuse to emit a decisive verdict when
  their own precondition failed, because the sentence gets quoted long after the caveat is forgotten.

- **Overlapping category labels cannot decompose a contrast between two of them.** Splitting the cohort by
  aetiology produced 3,437 label-assignments across 1,497 patients, and the "sepsis" group contained patients
  who were also anoxic — so comparing it against the anoxic group compared two overlapping sets and answered
  nothing. The corrected split (restrict to patients with NO anoxic label, then subdivide) gave a completely
  different and interpretable answer: 4/4 subgroups agreeing to within 0.03. Whenever a comparison is A versus
  not-A, the decomposition has to happen INSIDE not-A.

- **A finding that retrodicts a standing negative is worth more than one that adds a positive.** The aetiology
  reversal explains N10 — morphology's increment was +0.070 in all-anoxic I-CARE and +0.036 n.s. in mixed
  HEEDB, exactly what averaging two opposing effects produces. N10 had sat unexplained for months and was not
  used to build the account. That is the property this project had been demanding of a mechanism and never got
  from a candidate constructed to fit the positives.

- **Write the conclusion rule before the run, then check the rule itself for holes.** The registered rule for
  the reversal required external "agreement in direction", and I-CARE agreed in direction with an AUC of
  0.511 [0.464, 0.557] — an interval containing 0.5. The rule passed on evidence that establishes almost
  nothing. Pre-registration protects against moving the bar afterwards; it does not protect against setting it
  too low, and the second failure is easier to miss because the paperwork looks correct.

- **Check the ledger before recommending a resource, not after.** Four documents — CLAUDE.md, the handoff
  state, the research landscape and the queue — were written recommending TUH as the gating external
  replication for the aetiology reversal. TUH carries **no linked outcome data and no diagnosis field**, so
  it cannot replicate any outcome association at all, and this project had already established that at R321
  and recorded the same gate independently in LESSONS. The recommendation survived four documents and a
  handoff prompt because nobody re-read the record. The ledger exists precisely so that a resource is not
  re-evaluated from memory, and it only works if it is consulted before the claim, not after someone
  questions it.

- **Push after every step, because the container can roll the repository back.** A restart returned the
  working tree and local git to a commit from before the entire session — 33 commits and every analysis
  script gone locally. All of it was recoverable in one `git reset --hard origin/<branch>` because each step
  had been pushed as it completed. Had work been batched into one commit at the end, the session would have
  been lost. Treat `origin` as the only durable store, and the local tree as scratch.

- **The container can roll the git repository back to an arbitrary earlier commit, twice in one session.**
  Both times the working tree and local HEAD reverted to a commit predating hours of work while `/tmp` partly
  survived, so the failure looks like nothing happened rather than like an error. Everything was recoverable
  because each step had been pushed. **Two operational consequences.** First, `origin` is the only durable
  store — push after every commit, never batch. Second, **after any container restart, check `git log -1`
  before doing anything else**: work committed onto a rolled-back base lands on a stale tree, and an append to
  a stale ledger will silently drop every result logged in between. That happened here and was caught only
  because the push was rejected as non-fast-forward.

- **Caches in `/tmp` disappear independently of each other.** A restart left the 1 GB OMOP source table and
  the expensive morphology shards intact while deleting the three-minute aetiology cache derived from them.
  Scripts that depend on a derived cache should rebuild it themselves when it is missing rather than assert
  and exit — the next session should not have to work out which of thirty files evaporated.

- **Check whether a "structural limitation" is actually an extraction choice.** L3 — "every patient has an
  ascertained death; the outcome is how soon, not whether" — sat at the top of the limits table for months and
  bounded every aetiology analysis in the project. It was an artefact of which patient list a prior OMOP
  extraction had been run against: the source table on S3 covers the whole database, and re-extracting took
  sixteen minutes and gave 953 previously unlabelled survivors a measured aetiology. A limit that has been
  written down long enough starts being reasoned around rather than re-tested. Before accepting one, ask what
  produced it.

- **An assumption that turns out wrong, with the conclusion surviving, is stronger evidence than an assumption
  that turns out right.** R393 assumed patients with no diagnosis data were non-anoxic; 38.7 % of them were
  anoxic, so ~369 sat in the wrong arm. Correcting them moved the aetiology gap from +0.157 to +0.151. Had the
  assumption been correct, agreement between the assumed and measured analyses would have demonstrated almost
  nothing — the finding is instead shown robust to a misclassification easily large enough to have broken it.

- **When a variable is one clinicians act on, "it predicts outcome differently in group X" may be a fact about
  the guidelines, not the biology.** Burst suppression predicts death after anoxia and carries essentially
  nothing otherwise (+0.47 versus +0.05). That is a clean, actionable-looking result — and it is exactly what
  guideline-driven withdrawal would manufacture, because guidelines name burst suppression as malignant after
  cardiac arrest and nowhere else. The finding cannot distinguish the two in this design. What made the
  question answerable at all was having a second measure that **no clinician reads**, whose aetiology
  dependence cannot be behavioural. **Before reporting effect modification on a clinically actionable
  variable, ask whether the modifier also modifies clinician behaviour.**

- **An invisible predictor is a methodological asset, not just a curiosity.** The whole reason the
  self-fulfilling prophecy is unfalsifiable in this literature is that the predictors are the things
  clinicians see. A predictor requiring an FFT inside segmented bursts is immune by construction, and that
  property turned out to be worth more than any individual association it produced — it is the only reason
  the guideline result above can be interpreted at all.
