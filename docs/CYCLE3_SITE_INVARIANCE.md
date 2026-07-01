# Cycle 3 — Site-invariance correction and re-test (frozen CBraMod, HEEDB S0001↔I0002)

**Status: GATED-NULL on the clinical outcome + one genuine (INCREMENTAL) methods observation.**
Aggregate metrics only; all raw EEG/PHI stayed in scratchpad under the DUA. n = 327 patients
(S0001 = 239, I0002 = 88); one bag per patient = 24 windows × 400-d (mean+std of frozen CBraMod
encoder tokens). This is a 2-site pilot, not a generalizable study (see Limitations).

## What Cycle 2 left us
Frozen embeddings encoded **hospital** almost perfectly (linear site-probe AUC 0.961) → any cross-site
outcome AUC was confounded. Cycle 3 applied the pre-registered Route-A site-correction and re-tested,
then aggressively red-teamed the result.

## Result 1 — Linear site-harmonization gives FALSE assurance of site-invariance (methods observation)
Correction fit on the S0001 reference windows only; I0002 aligned via the new-site transform (its own
location/scale, **no outcome used** → no firewall breach). Site-probe = predict which hospital.

| Correction | **Linear** logistic site-probe | **Nonlinear** attention-MIL site-probe (3 seeds, 5-fold OOF) |
|---|---|---|
| RAW (uncorrected) | 0.961 | 0.930 [0.915, 0.941] |
| ComBat (1st/2nd moment) | **0.585** | **0.964 [0.932, 0.990]** |
| CORAL (2nd-order covariance) | **0.585** | **0.991 [0.984, 1.000]** |

**Reading.** Both linear/2nd-order harmonizers collapse the *linear* probe to ≈chance (0.585) — which
naively "passes" a ≤0.6 site-invariance gate — yet a nonlinear model still recovers hospital at
**0.96–0.99** from the *same* corrected embeddings. CORAL, which matches covariance, actually makes the
residual site structure *more* nonlinearly separable (0.991). **A site-invariance gate that uses only a
linear probe is badly misleading; the gate must be nonlinear.**

Note the measured nonlinear residual is a **lower bound**: the correction was fit once (not per-fold), and
the only leakage (I0002 aligned using all-I0002 stats) makes the two sites *more* similar, so it can only
*reduce* the measured site-AUC. True residual recoverability is ≥ the numbers above.

## Result 2 — No strong cross-site clinical-outcome signal survives (power-calibrated null)
Outcome MIL on ComBat-corrected embeddings (5-fold OOF): abnormal-EEG 0.435 (degenerate, 295/327 positive
— dropped as uninformative); cognitive/behavioral-syndrome ICD-10 0.466 (25/327 positive; permutation-null
band [0.349, 0.591] → indistinguishable from chance). In-sample also ≈chance.

**Is that "no signal" or "underpowered"?** Injected-signal calibration at the real n=25-positive regime
(same MIL + OOF + permutation pipeline):

| Injected effect (per-feature σ) | OOF AUC recovered |
|---|---|
| 0.00 (control) | 0.460 |
| 0.15 | 0.475 |
| 0.30 | 0.586 |
| 0.60 | 0.842 |

The pipeline **detects effects ≥ 0.30σ (natural AUC ≳ 0.59) but misses smaller ones** at this n. Therefore
the cognitive null **excludes a strong frozen-embedding cognitive signal, but cannot exclude a weak one.**
Distinguishing "weak signal present" from "no signal" requires more labeled positives, not a new probe.

## Hostile-review verdicts (independent sub-agent panel)
- **Novelty (prior-art sweep): INCREMENTAL, high practical value.** The exact demonstration (nonlinear probe
  unmasks residual site after ComBat, on EEG-foundation-model embeddings) is **unpublished**; closest is
  Murchan et al. 2024 (pathology embeddings: pre-ComBat site-AUC 0.96 → post 0.506, declared success,
  **never ran a nonlinear probe**). ComBat-removes-only-location/scale is 20-year textbook, so this is a
  methods *safeguard*, not a discovery. Cross-site EEG-FM clinical-outcome validation is genuine white space
  (0 PubMed hits). Refs: Murchan 2024 (JPI); An 2024 DeepResBat (Med Image Anal); Jaramillo-Jimenez 2024
  (Clin Neurophysiol); Nugent 2026 (Imaging Neurosci); Johnson 2006 (ComBat).
- **Methods red-team: Claim A = MAJOR-REVISION, Claim B = KILL-as-a-standalone-null.** A must be reframed
  from "discovery" to "empirical demonstration + gate recommendation," and needs per-fold refit + bootstrap
  CIs + ≥3–5 sites before it is a publishable methods note (2 sites confound site with every between-site
  variable). B is underpowered as shown; the calibration above is the fix and bounds what it can claim.

## Honest bottom line
1. The **frozen + CPU** path **cannot** deliver a positive cross-site clinical-outcome finding at this n:
   the usable site-invariant outcome signal is at most weak and undetectable with 25 positives.
2. The one genuine contribution is the **nonlinear-gate safeguard** — best placed as the *site-invariance
   gate* methods section of the main pre-registered study (with per-fold CIs + more sites), not a headline.
3. The real levers for a positive finding are unchanged and now **evidence-backed**: (a) far more labeled
   positives (larger multi-site cohort), and (b) **encoder fine-tuning (GPU)** — the frozen representation
   is demonstrably site-dominated and outcome-poor.

The machine's gate did its job: it refused to claim a finding that isn't there, and it converted the
failure into a calibrated, reusable lesson.
