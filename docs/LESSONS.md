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
