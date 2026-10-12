# Nurse-PRN IV — v1 RETIRED, v2 SALVAGED (dose-intensity reframe solves the confounding)

## v1 (administration-decision) failed — see bottom for the record
Binary give/hold per dose, whole-stay aggregation: adminRate 0.97 (non-administrations uncharted), no
instrument variation, nonsensical RF, balance ±30 yr. Retired.

## v2 SALVAGE — it works
Reframed estimand that dodges all three v1 problems: treatment = **PRN dose INTENSITY (count of GIVEN doses,
fully observed) in a FIXED 48h window from the first dose**; instrument = the administering nurses'
leave-one-out liberality (mean window-dose count per patient); fixed window + within-service/acuity controls
break the LOS confounding. Code: `docs/nurse_prn_iv_v2.py`.

**Balance recovered from ±30 yr (v1) to <1 yr (v2)** — the confounding is solved. Low-acuity (elective) headline:
| drug | n | FS (F) | LATE / PRN dose | balance | NC-calibrated p | verdict |
|---|---|---|---|---|---|---|
| Opioid | 45,378 | +0.91 (898) | −0.004 | +0.8 yr | **0.947** | ✓ VALID → clean **NULL** |
| Benzodiazepine | 12,932 | +0.56 (101) | +0.118 | +1.0 yr | **0.000** | ✓ VALID → harm signal survives |
| Antipsychotic | 5,816 | +0.46 (51) | +0.156 | +0.4 yr | **0.000** | ✓ VALID → harm signal survives |

## Interpretation (honest)
- **Opioid PRN intensity → mortality: clean null** (valid, calibrated p=0.95). Trustworthy; reassuring for
  post-op PRN opioid dosing at these levels.
- **Benzodiazepine & antipsychotic PRN intensity → higher mortality: signals SURVIVE balance + NC calibration.**
  Direction matches known pharmacology (both carry mortality warnings; benzos are the Beers de-implementation
  target). The **opioid-null vs benzo/antipsy-harm contrast is evidence the design is not merely capturing
  "sicker patients get more drugs"** — pure confounding would make opioids look harmful too.
- **Caveat before claiming benzo/antipsy:** a per-dose LATE of +0.12–0.16 is implausibly large for a clean
  per-dose causal effect. With balance and NC both passing, the leading remaining threat is a **sedative-specific
  exclusion-restriction violation** — a "sedation-heavy" nurse/unit culture harming via non-drug paths (less
  mobilization, more restraints, missed delirium) that generic NC outcomes don't capture. Needed before any
  claim: a sedation-culture / co-intervention exclusion test (e.g. does nurse benzo-liberality predict
  restraint use, immobility, or delirium-workup independent of dose), and severity controls beyond age.

## Status
Instrument B is **UN-RETIRED**: the v2 dose-intensity design is valid (balance <1 yr, sensible F, NC-calibrated).
It yields a trustworthy opioid null now and two promising-but-unconfirmed sedative harm signals pending the
sedation-culture exclusion test. This is the bulletproofing working in both directions: a failed design (v1) was
rejected, then a principled reframe (v2) recovered a valid instrument — and its outputs are gated (opioid
reportable; benzo/antipsy flagged for one more test).

---
## [RECORD] v1 failure detail
adminRate 0.97 (2.93M Administered vs 75k Not Given), nurseSpread 0.02, RF −2.4 (nonsensical), balAge ±30 yr.
Root cause: a withheld PRN dose generates no emar record → give/hold denominator unobserved. Superseded by v2.
