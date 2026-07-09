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

## Results (feasibility probe)
_Pending the scaled (N=50/class/site) run; tiny pilot (N=6) already gave cross-site AUC 0.74–0.79 with post-filter
amplitudes physiological — to be confirmed/hardened below._
