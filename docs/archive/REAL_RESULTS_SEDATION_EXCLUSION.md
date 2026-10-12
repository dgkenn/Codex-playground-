# Sedation-culture exclusion test — benzo/antipsy harm signal is robust but NOT yet claimable

The nurse-PRN dose-intensity IV flagged benzodiazepine and antipsychotic harm signals (LATE +0.12–0.16/dose)
that survived balance + NC calibration. Before claiming, the key threat was a **sedation-heavy nurse/unit
culture** harming via the whole bundle (benzo+opioid+antipsy, restraints, immobility), not the target drug.
Test (`docs/sedation_exclusion.py`, real emar):

| test | result | read |
|---|---|---|
| **A. drug-specificity** (nurse liberality corr across sedatives) | benzo–opioid +0.25; **benzo–antipsy +0.73**; opioid–antipsy +0.19 | a shared sedation culture exists (benzo↔antipsy) |
| **B. leakage** (co-sedative doses ~ Z) | benzo −0.57; antipsy −0.43 | NEGATIVE → benzo-liberal nurses SUBSTITUTE, don't pile on (supports specificity) |
| **C. robustness** (LATE +co-sedation control) | benzo +0.137→**+0.123**; antipsy +0.129→**+0.125** | SURVIVES → drug-specific, not the co-sedation drug bundle |

## Verdict: robust lead, NOT a claimable causal finding
- The harm signal is **drug-specific and survives the co-sedation-drug control** (test C) — more than a pure
  confounding artifact, and consistent with the known benzo/antipsy mortality literature.
- **BUT it is not claimable**, for two honest reasons:
  1. **Non-drug culture channels are untested** — restraints, immobility, missed-delirium monitoring are exactly
     how a sedation culture would harm, and they live in `chartevents` (ICU-only, not available here). Test C
     rules out the drug bundle, not these.
  2. **The effect size is implausibly large** (+0.12–0.14 mortality *per dose*) for a clean per-dose causal
     effect → residual confounding almost certainly remains (unmeasured severity or the untested channels).

## Implication
The benzo/antipsy de-implementation harm is a **strong, mechanistically-plausible LEAD for future work** (needs
restraint/mobility data to test the non-drug channels), NOT the program's clean clinical headline. The
trustworthy nurse-PRN result remains the **opioid PRN-intensity NULL** (clean, calibrated). Honest scoping again:
the toolkit reports what survives and flags what doesn't.
