# Sodium cross-method IV — FAILS the gate (pseudo-dysnatremia + acuity); the landmark-via-open-question test

This was the decisive test of whether the bulletproof cross-method instrument could be pointed at an **open**
clinical question (dysnatremia management, not settled by a mortality RCT) rather than the already-settled
transfusion question. **Verdict: sodium is not a clean instrument — the landmark-via-sodium path is closed.**

## Design
Chemistry Na (50983, **indirect ISE**) vs blood-gas Na (50824, **direct ISE**) within 1h. Two reflexive
decisions with observable treatments: HYPOnatremia (Na<130 → hypertonic saline 225161/228341) and
HYPERnatremia (Na>150 → free water 225797/225944). Both instrument directions; gate battery = cross-method σ,
first stage, flag-ITT (30d mortality), age balance, and the NC gate (does the Na flag predict RBC transfusion,
a Na-independent treatment?).

## Result — NC fires in every configuration
| decision | direction | first stage (F) | balAge | **NC-RBC** |
|---|---|---|---|---|
| hypoNa (Na<130) | chem-flag | +0.003 (F≈0) — no relevance | −1.99 | **−0.112 FIRES** |
| hypoNa | bloodgas-flag | +0.005 (F≈1) — no relevance | +1.21 | **+0.049 FIRES** |
| hyperNa (Na>150) | chem-flag | +0.092 (F=12) — has relevance | +1.34 | **+0.094 FIRES** |
| hyperNa | bloodgas-flag | −0.009 (F≈0) | −0.56 | **−0.072 FIRES** |

Cross-method σ = **2.26 mEq/L** — much larger than the ~1 mEq/L expected from analytic imprecision alone.

## Mechanism — two reasons, both fatal
1. **Pseudohyponatremia / ISE divergence:** chem Na is *indirect* ISE (diluted sample), which reads falsely low
   with high lipids/protein; blood-gas Na is *direct* ISE (whole blood), which does not. Their discordance is
   therefore partly a lipid/protein artifact — the sodium analogue of potassium's hemolysis — correlated with
   the sickest patients. The inflated σ (2.26) is the fingerprint.
2. **Dysnatremia is itself a severity marker:** even conditional on the other method's Na, being flagged
   severely hypo-/hyper-natremic carries acuity information (these patients are sicker), so the flag predicts
   downstream care (RBC transfusion) it should not — the NC fires at ~5× the magnitude potassium did (−0.11 vs
   +0.02). This is more fundamental than an assay artifact and cannot be screened away.
3. **Separately, hyponatremia has no observable reflexive treatment:** it is managed mostly by fluid
   restriction / stopping hypotonic fluids (unobservable in inputevents), so hypertonic saline (0.6–0.8%) gives
   no first stage regardless.

## Strategic consequence
The cross-method assay-noise instrument is clean **only** where the two methods share measurand *and* failure
modes and the flag is not itself a strong acuity marker — which, on the available MIMIC analytes, is **Hb
alone** (co-oximetry vs impedance, both intact hemoglobin, transfusion decision). Every open-question candidate
tested (K, Na) fails via an analyte-specific artifact + acuity leakage. This closes the "point the bulletproof
instrument at an unsettled question" route on MIMIC: the one clean instrument sits on the most-RCT'd decision
(transfusion). The realistic high-value output is therefore the **rigorous methods paper** — "when can a
cross-method noise instrument be trusted," empirically mapped across ≥5 analytes with mechanisms — plus external
multi-site validation of the Hb result; not a landmark answer to a new clinical question via this instrument
family. (The EEG-foundation-model cross-site line in CLAUDE.md remains the separate, GPU-gated landmark route.)
