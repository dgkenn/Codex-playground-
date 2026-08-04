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

## Result 3 — Positive-control outcomes reveal the REPRESENTATION is the bottleneck (added post-red-team)
Sanity check demanded by the red-team: run outcomes EEG is *known* to encode (age, sex) through the
identical MIL+OOF pipeline. If the harness recovers them, the clinical nulls are about signal/power, not a
broken pipeline.

| Target | ALL sites (n=327) | S0001-only (no site confound, n=239) |
|---|---|---|
| Sex | 0.499 | 0.501 |
| Age > median | 0.555 | 0.610 |

EEG decodes sex at ≈0.70–0.85 and age strongly in the literature — but the frozen **mean+std per-window**
embeddings recover sex at **chance** and age at only **0.55–0.61**. Age is balanced at n=327, so this is
**not** a power problem. Paired with the injected-signal calibration (the harness recovers a 0.6σ additive
signal at 0.84, so the harness is *not* broken), the conclusion is that the **frozen mean+std representation
is impoverished** — it discards most of the usable EEG structure.

**Key fork this opens (CPU-runnable):** the culprit may be my **mean+std pooling** (collapsing the 19×30
per-window tokens to 400-d), *not* the frozen CBraMod encoder itself. Next experiment = a **full-token
attention-MIL** (attend over all tokens, no mean+std collapse) and re-run the age positive control:
- age recovers well (≳0.75) → the pooling was the bottleneck, fixable **on CPU**; redo the outcome tests
  with full tokens before concluding anything about the frozen encoder.
- age still ≈0.6 → the frozen encoder itself is insufficient → **encoder fine-tuning (GPU)** is required.

## Honest bottom line
1. The **frozen mean+std** representation is site-dominated (nonlinearly) AND outcome-poor — it barely
   encodes even age. No positive cross-site clinical finding is reachable from it at this n.
2. **CPU path now exhausted (Cycle-4 decider settled the fork).** A clean matched comparison (same
   patients/windows/folds; mean+std vs channel-resolved full-token) gave age OOF AUC 0.401 vs 0.476 at
   n=98 — both ≈chance. Richer pooling is NOT the lever; the frozen CBraMod *encoder* is the ceiling.
   A positive cross-site clinical finding requires **encoder fine-tuning (GPU)**.
3. The one genuine methods contribution is the **nonlinear-gate safeguard** — best placed as the
   *site-invariance gate* section of the main pre-registered study (with per-fold CIs + more sites), not a
   headline. Novelty INCREMENTAL.
4. Evidence-backed lever ordering for a positive finding: (a) full-token frozen MIL [CPU]; (b) larger
   multi-site labeled cohort, mortality as the better-powered endpoint [CPU]; (c) encoder fine-tuning [GPU].

The machine's gate did its job: it refused to claim a finding that isn't there, and it converted the
failure into a calibrated, reusable lesson.
