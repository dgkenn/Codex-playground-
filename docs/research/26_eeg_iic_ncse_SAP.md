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

## Decisive next experiments (ranked)
1. **Amplitude-matched hard contrast** (GPD/LPD vs GENSLOWING at matched median-µV) — does CBraMod beat amplitude
   when amplitude can't separate? (CPU, ~1 run; decides whether frozen embeddings suffice.)
2. **Fine-tune CBraMod** on the labeled IIC classes with site-held-out eval (GPU) — the expected performance lever.
3. **Outcome-anchoring** — re-label the IIC gray zone by hard reference (seizure progression / neuronal-injury
   biomarker / mortality) and test whether the model resolves expert disagreement by true consequence. This is
   the practice-changing study; the classifier above is the enabling step.
