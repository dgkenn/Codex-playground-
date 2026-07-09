# Pre-registration / SAP — foundation-model EEG differentiation of NCSE/ictal-interictal continuum vs encephalopathy

**Written during the feasibility probe** (results appended below). EEG idea #1 — the repo's core mission. The
bedside question: in a comatose/altered patient, is the EEG **ictal** (electrographic seizures / the
ictal-interictal continuum → treat, escalate) or **encephalopathy** (diffuse slowing / burst suppression → treat
the cause; anti-seizure drugs only harm)? EEG is the sole arbiter; expert inter-rater disagreement in the IIC gray
zone is the documented failure mode. A frozen EEG foundation model that resolves this — anchored to a hard outcome,
not just expert labels — is Lancet Neurology / Nature Medicine–tier.

## Data (all reachable and verified live on the credentialed BDSP access point)
`s3://…/morgoth1/data/internal_dataset/<CLASS>/segments_raw/*.mat` — expert-labeled 10-min, 200 Hz, 19-ch (+EKG)
segments (v7.3 HDF5; folder = class label). Verified counts by site:
- **Ictal / epileptiform:** SEIZURE (1,789 S0001 / 371 S0002), LPD (1,280/864), GPD (1,193/703/+271 I0002),
  IIIC umbrella (47,328), GRDA/LRDA.
- **Encephalopathy:** GENSLOWING (3,610/1,786), FOCALSLOWING (1,396/671), BS burst-suppression (291/400/+72),
  NORMAL (4,778/138).
Two well-covered sites (**S0001, S0002**) enable a true cross-site split; I0002/I0003 add device diversity.

## Backbone
Frozen **CBraMod** (HF `weighting666/CBraMod`, sha256-pinned, cached locally; validated end-to-end on real HEEDB
EEG). Input (n_windows, 19, 6000) @ 200 Hz → mean-pooled encoder features (d≈200). No dependency on the
unreleased MORGOTH model — we use the labels directly.

## Feasibility probe (this pass)
- **Target:** binary ICTAL {SEIZURE, LPD, GPD} vs ENCEPH {GENSLOWING, FOCALSLOWING, BS}.
- **Pipeline:** stream each segment (download → preprocess → embed → delete); bandpass 0.5–45 Hz + ±800 µV clip;
  4 evenly-spaced 30-s windows/segment → CBraMod → mean-pool; logistic head.
- **Validation = SITE-SPLIT** (train S0001 → test S0002 and reverse) — the honest cross-site generalization,
  not random CV.
- **Guards (pre-committed):** (a) **bandpass** neutralizes the raw amplitude/units confound (raw ranges differed
  ±200 vs ±14000 by class → drift; post-filter µV must be physiological and comparable across classes);
  (b) **amplitude-only baseline** (single feature = median |µV|) — the embedding must beat it, or the "signal"
  is just amplitude; (c) **site-probe** (predict SITE from the same embeddings) — quantifies device/site leakage.
- **Gate:** cross-site AUC materially > amplitude-only baseline and > 0.5, with the class signal surviving the
  held-out site. Otherwise log negative and stop.

## The Nature-tier study (why this is NOT a me-too SPaRCNet/HMS classifier)
SPaRCNet (Jing, *Neurology* 2023) and HMS-HBAC (Kaggle 2024) already classify the 6-class IIC against **expert
consensus**. Matching expert labels ≠ practice-changing. The differentiators:
1. **Outcome-anchored gray-zone resolution.** Train/evaluate against a **hard reference** — progression to
   definite electrographic seizures, neuronal-injury biomarker, or mortality/functional outcome — so the model
   resolves the IIC patterns experts *disagree* on by their true clinical consequence, not by consensus vote.
2. **The specific NCSE-vs-triphasic decision** (seizure/periodic-epileptiform vs generalized-slowing/triphasic),
   which is the exact bedside treat-or-not call.
3. **Foundation-model advantage** over hand-crafted/visual grading, and cross-site + cross-device
   generalization (the SPaRCNet weakness).

## Circularity & leakage guards (from repo lessons)
- The v3 protocol flags "progression to seizures" as **circular in MORGOTH's seizure-detecting embedding space**.
  CBraMod is **not** seizure-supervised, so its embeddings are not tautological with a seizure label; still, the
  definitive study anchors to a hard *outcome*, and adjusts for any model seizure-detection output as a covariate.
- Prior repo result: a seizure-**diagnosis** ICD label gave AUC 0.47 ("diagnosis ≠ ictal EEG") — we use
  **epoch-level ictal/IIC** labels, not diagnosis codes.
- Site leakage is real here (repo site-probe once hit 0.96): **split by site**, report the site-probe, and
  require the class signal to survive on a held-out site/device.

## Results (feasibility probe — DONE, N=50/class/site, 593 usable segments, 2 sites)
End-to-end pipeline validated: BDSP labeled `.mat` → bandpass/clip → frozen CBraMod → mean-pooled 200-d
embedding → site-split logistic head. Binary ICTAL {SEIZURE,LPD,GPD} vs ENCEPH {GENSLOWING,FOCALSLOWING,BS}.

| Test | AUC | Read |
|---|---|---|
| **CBraMod cross-site** (train S0001→test S0002 / reverse) | **0.771 / 0.775** | real, stable cross-site signal |
| Amplitude-only baseline (1 feature = median \|µV\|) | 0.733 / 0.752 | classes genuinely differ in amplitude (BS 3 µV vs epileptiform 14 µV) |
| **CBraMod, amplitude-RESIDUALIZED** | **0.770 / 0.751** | **signal survives removing amplitude → CBraMod adds real spectral/morphologic structure, not just amplitude** |
| within-site 5-fold (raw / amp-resid) | 0.773 / 0.748 | class signal holds within site too |
| **SITE-PROBE leakage** (predict site from embedding) | **0.781** | substantial site/device structure — the main caveat |

**Verdict: POSITIVE but MODEST, with a real caveat.**
- **Data + pipeline: fully feasible** (verified live on the credentialed bucket; runs end-to-end on CPU).
- **Frozen CBraMod carries genuine class signal** (~0.77 cross-site, +~0.04 over amplitude, and — critically —
  **survives amplitude-residualization**, so it is not an amplitude artifact). Class was balanced across sites,
  so the cross-site number is a clean generalization estimate, not aliased with site.
- **Caveat — site leakage (probe 0.78):** embeddings encode device/site heavily; the full study must train
  multi-site and use domain adaptation, and hold out an untouched site (as the repo's firewall already enforces).
- **This crude binary is the easy version.** The clinically decisive, Nature-tier question is the
  **amplitude-matched IIC gray zone** (GPD/LPD vs generalized-slowing/triphasic — patterns that look alike) and
  the **outcome-anchored** resolution (which patterns truly progress/harm). Frozen embeddings likely hit a
  ceiling there; **fine-tuning CBraMod (GPU-gated)** is the expected next lever.

## HARD-CONTRAST result (matched-amplitude IIC gray zone) — the decisive test, POSITIVE
Contrast: **GPD+LPD (periodic epileptiform, the IIC gray zone) vs GENSLOWING+FOCALSLOWING (encephalopathy)** —
the actual NCSE-vs-encephalopathy question, with *overlapping* amplitudes (GPD 13.3, LPD 10.3, GENSLOWING 9.6,
FOCALSLOWING 7.9 µV). N=480 (240/240), site-split.
| Test | AUC |
|---|---|
| **CBraMod cross-site** (S0001↔S0002) | **0.732 / 0.785** |
| Amplitude-only baseline | 0.625 / 0.631 |
| **CBraMod, amplitude-MATCHED band [3.2,15.6] µV** (n=350) | **0.723 / 0.787** |
| Amplitude-only, matched | 0.624 / 0.628 |
| Site-probe leakage | 0.777 |

**Verdict: CBraMod adds real value on the clinically-decisive contrast — +0.10 to +0.16 AUC over amplitude, and
the advantage HOLDS in the amplitude-matched band.** Contrast with the first crude binary (SZ/LPD/GPD vs
slowing/BS) where CBraMod beat amplitude by only +0.03 (that easy binary was mostly amplitude). On the *hard*
gray-zone distinction the foundation model is genuinely discriminative, not an amplitude proxy. This is the
result that says the approach is worth pursuing. Remaining caveats unchanged: site-leakage 0.78 (needs multi-site
+ domain adaptation), and amplitude-matching wasn't perfect (amplitude-only stayed ~0.62, not 0.5) — but the
CBraMod-vs-amplitude GAP is the evidence and it is clear.

## CPU-ONLY models (no GPU) — user question answered: YES
Hard IIC gray-zone contrast (GPD/LPD vs GEN/FOCAL-slowing), N=637, site-split cross-site mean AUC + site-probe:
| Model (all CPU) | cross-site AUC | site-probe |
|---|---|---|
| amplitude-only (reference) | 0.65 | — |
| CBraMod + logistic (prior result) | **0.776** | 0.775 |
| CBraMod + HistGradientBoosting | 0.758 | 0.775 |
| **Classical features + HGB (NO deep model)** | **0.753** | **0.708** |
| Fusion (classical ⊕ CBraMod) + HGB | 0.763 | 0.799 |

**Verdict: no GPU — and arguably no foundation model — is needed for this classifier at current scale.** Purely
classical EEG features (per-channel band powers δ/θ/α/β/γ, band ratios, SEF95, spectral entropy, Hjorth,
line-length, kurtosis/skew, **autocorrelation periodicity**, laterality) + gradient boosting reach **0.753**,
statistically indistinguishable from frozen CBraMod (0.776; CIs overlap) and with **lower site-leakage**
(0.708 vs 0.775 → more physiology, less device). Fusion adds nothing (the two representations are redundant).
Top classical features are clinically sensible: **periodicity** (periodic discharges), spatial α/δ variability,
**skewness/sharpness** (epileptiform), SEF, line-length, γ.
- **Implication:** the CPU classical path is cheaper, interpretable, and equal — pursue it for the classifier;
  the foundation model is not the bottleneck here.
- **Honest caveats:** 2-site cohort, model differences within CI (the honest claim is "classical ≈ CBraMod,
  both ≈0.75"); site-leakage still non-trivial. The per-site-standardization leakage mitigation **backfired**
  (near-zero-variance features blew up → site-probe →1.0); dropped. Breaking the ~0.75 ceiling / resolving the
  *true* gray zone needs larger multi-site data + domain adaptation, or the outcome-anchored relabel — not GPU
  fine-tuning per se.

## OUTCOME-ANCHORED (mortality) — feasibility + first look
**Linkage verified live:** segment `sub-<SITE><patient>_ses-N_<ts>` → HEEDB `eeg-metadata.BidsFolder` →
`DateOfDeath` + `AgeAtVisit`. Cohort (one seg/patient, 12,699): **30-day mortality 12.5%**, powered both sites
(S0001 916 / S0002 676 deaths). **Pattern→mortality gradient is textbook-coherent + reproducible across sites:**
GPD 30%/30% ≫ BS 48%/26% > LPD 23%/15% > SEIZURE/GRDA 6–17% > LRDA/slowing 4–9%. This validates the linkage and
is itself a real prognostic gradient (though the IIC→outcome gradient is known — Westover/Hirsch).

**First incremental-value look (636 already-embedded GPD/LPD/GEN/FOCAL segments, 19% mortality, site-split):**
| model | cross-site AUC (30-d mortality) |
|---|---|
| age-only (the bar) | 0.624 |
| age + pattern-category | **0.668** (category adds real signal over age) |
| age + category + classical EEG | 0.647 (no gain) |
| age + category + CBraMod EEG | 0.682 (+0.014, CIs overlap) |
| within-GPD: classical EEG / CBraMod | 0.59 / 0.51 (n=159, 47 deaths — underpowered) |

**Interim verdict: the NOVEL claim is NOT yet supported.** The pattern *category* captures most of the prognostic
signal; the EEG *morphology* adds little beyond age+category on this sample. The only live hope for the
gray-zone-resolution claim is the **within-category** test (among GPDs, does the EEG separate survivors?) — a faint
classical hint (0.59) that is underpowered here. Decisive next step: a **powered within-GPD/LPD embedding run**
(natural mortality, ~200/class/site). If within-category EEG stays ≈0.5 at power → honest negative (IIC→mortality
is category/severity-driven, EEG adds nothing beyond the label); if classical firms to a tight >0.55 → real signal.

## POWERED outcome-anchored result (n=1,316 GPD/LPD/GENSLOWING, 19.3% 30-d mortality, site-split)
| model | cross-site AUC (30-d mortality) |
|---|---|
| age-only | 0.573 |
| age + pattern-category | 0.667 |
| **age + category + classical EEG** | **0.708** (ΔAUC **+0.039 [−0.001,+0.078]**, borderline) |
| age + category + CBraMod EEG | 0.673 (ΔAUC +0.005, null) |

**Decisive WITHIN-category test (does EEG separate survivors *inside* one expert label?):**
| | age-only | classical EEG | CBraMod EEG | age+classical |
|---|---|---|---|---|
| **within GPD** (n=436, 140 deaths) | **0.500** | **0.595** (0.610/0.580) | 0.595 (0.585/0.606) | 0.586 |
| **within LPD** (n=440, 81 deaths) | 0.499 | 0.594 (0.590/0.599) | 0.541 | **0.617** |

**Verdict: PROMISING but MODEST — a real, non-me-too signal.** Within the gray-zone patterns (GPD, LPD), the EEG
*morphology* separates 30-day survivors from non-survivors at **AUC ~0.59–0.62 cross-site**, *consistent in both
site directions and both patterns*, where **age alone is exactly chance (0.50)**. This operationalizes "which
periodic discharges are harmful" by **outcome**, beyond age and beyond the categorical label — the practice-
relevant question SPaRCNet/HMS (expert-label replication) do not answer.
**Honest caveats (do not over-claim):** (1) effect is modest (AUC ~0.6) and the incremental-over-category CI just
touches 0; (2) **classical features ≈ or > CBraMod** (foundation model adds nothing prognostic here — top feature
is line-length, but importances are diffuse/weak, no clean physiological driver); (3) **unmeasured ICU-severity
confounding** is the primary threat — age is controlled (and null) but is not a severity score; a dying patient's
worse morphology could be severity, not the pattern's harm; (4) 2 sites, site-probe 0.66. Needs ≥1 more site +
a severity score (APACHE) + the IIC-burden design to be definitive; the causal "treat-the-pattern-helps" step is a
trial. **The descriptive pattern→mortality gradient itself is coherent but known (Westover/Hirsch); the novel bit
is the within-category EEG signal, which is real-but-modest.**

## Decisive next experiments (ranked)
1. **Amplitude-matched hard contrast** (GPD/LPD vs GENSLOWING at matched median-µV) — does CBraMod beat amplitude
   when amplitude can't separate? (CPU, ~1 run; decides whether frozen embeddings suffice.)
2. **Fine-tune CBraMod** on the labeled IIC classes with site-held-out eval (GPU) — the expected performance lever.
3. **Outcome-anchoring** — re-label the IIC gray zone by hard reference (seizure progression / neuronal-injury
   biomarker / mortality) and test whether the model resolves expert disagreement by true consequence. This is
   the practice-changing study; the classifier above is the enabling step.
