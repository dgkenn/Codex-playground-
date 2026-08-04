# Statistical Analysis Plan — Hemodynamic & racial occult hypoxemia (eICU → MIMIC-IV)

**Status:** pre-registered before the confirmatory run (this session). Reference-validity gate PASSED for eICU
(measured co-oximetry SaO₂; see `docs/LESSONS.md` and ledger). VitalDB/INSPIRE FAILED the gate (calculated SaO₂).

## One-sentence claim under test
Pulse oximetry (SpO₂) systematically **overestimates** true arterial saturation (co-oximetry SaO₂) — and the error
is **amplified in low-perfusion states** (low MAP / vasopressor infusion), the same low-flow conditions in which the
oscillometric cuff also over-reads pressure (finding C8) — producing **occult hypoxemia** that is missed at the
bedside, disproportionately in Black patients, with a mortality signal. This is a *unified failure of noninvasive
monitoring in low flow*, of which racial pulse-ox bias (Sjoding NEJM 2020) is one axis and hemodynamics is the
novel, mechanistic second axis.

## Why this can clear the top-tier bar (and why the EEG ideas could not)
- **Independent gold standard:** co-oximetry SaO₂ is a physically independent instrument from the pulse oximeter
  (the discriminator that separated C8/cuff [won] from the EEG depth-monitor ideas [same-device reference, capped]).
- **Confound-immune (RTM-safe) design:** condition on the SaO₂ reference; never bin on the noisy SpO₂.
- **Hard outcome + mechanism + multi-site replication** (eICU 154 hospitals → MIMIC-IV).
- **Not GPU- or EEG-credential-gated** — data is in hand.

## Data
- **eICU-CRD v2.0** (primary): `lab` (co-oximetry SaO₂ = "O2 Sat (%)", paO₂, pH, COHb, MetHb), `vitalPeriodic`
  (pulse-ox SpO₂ col `sao2`, invasive MAP `systemicmean`), `patient` (ethnicity, age, hospital, mortality),
  `infusionDrug` (vasopressors). **MIMIC-IV** (external): `labevents` (co-oximetry SaO₂ 50817, paO₂, pH),
  `chartevents` (SpO₂ 220277, MAP), `patients`/`admissions` (race, mortality).
- **Pairing:** each ABG draw → nearest SpO₂ (and MAP) within [−10, +2] min. Measured co-oximetry only (gate applied).

## Endpoints
1. **Bias:** mean (SpO₂ − SaO₂) by true-SaO₂ stratum (Bland-Altman). Primary descriptive.
2. **RTM-safe miss rate (primary):** P(reassuring SpO₂ ≥ 92% | true SaO₂ < 88%), by race and by perfusion.
3. **Sjoding occult rate (secondary):** P(SaO₂ < 88% | SpO₂ 92–96%), by race and by perfusion.
4. **Hemodynamic amplification (the novel test):** miss rate and bias across MAP tertiles and vasopressor
   on/off, **within race strata** (does low flow amplify the miss independent of race?).
5. **Consequence:** mortality among true-hypoxemia draws, occult (SpO₂ ≥ 92) vs detected (SpO₂ < 92), patient-level
   dedup + age/severity (APACHE) adjustment. Hypothesis-generating, not causal.

## Pre-specified confound controls & threats
- **Patient-level clustering:** dedup to one index event/patient for outcome models; cluster-robust or mixed models.
- **Severity confound (occult ⇢ mortality):** adjust APACHE/age; report within-perfusion-stratum so severity is
  partially matched; frame consequence as associational.
- **Perfusion↔severity collinearity:** the *measurement* endpoints (1–4) are confound-immune (condition on SaO₂);
  only the consequence endpoint (5) is severity-threatened — labeled as such.
- **Signal-quality / motion:** require paired SpO₂ within window; sensitivity to [−5,0] min tighter window.
- **Reference validity:** pH-correction gate re-run in MIMIC-IV before use (INSPIRE/VitalDB failed it — do not skip).
- **Skin-tone vs race:** eICU/MIMIC record race, not skin tone; state as a proxy limitation (same as Sjoding).

## Decision gates
- **Alive** if: bias > 0 and increasing at low SaO₂; miss rate rises with lower MAP / vasopressor **within race**;
  replicates directionally in MIMIC-IV.
- **Kill / downgrade** if: perfusion effect vanishes after any reasonable adjustment (then it is just Sjoding
  re-replication, not new); or SaO₂ fails the MIMIC gate; or the effect is an artifact of pairing window / signal
  quality.

## Non-goals
No new SpO₂ device; no causal claim about correcting SpO₂ improving outcomes (that is a trial); no skin-tone claim
beyond the recorded race proxy.
