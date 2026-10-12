# PIC pediatric calcium: age-dependent correction factor — does refining it help? (NO)

**Status:** STRIKE-OUT on the clinical headline (honest negative). The age-dependence of the albumin/Ca binding
slope replicates and is real, but deriving an age-corrected formula does NOT improve classification against
ionized-calcium ground truth — because albumin-corrected calcium (any factor) poorly tracks ionized in children.
Reinforces the seam-wide lesson: refining a biased correction ≠ a clinical win; measure the ground truth.

## Data
PIC (Paediatric Intensive Care, PhysioNet picdb/1.1.0). Streamed LABEVENTS, filtered to itemids 5215 ionized Ca
(mmol/L, ground truth), 5034 total Ca (mmol/L), 5024 albumin (g/L); PATIENTS for DOB→age. SI→US conversion:
total mg/dL = mmol/L×4.008, albumin g/dL = g/L/10. Triple-paired within 4h: **N=23,980 (9,227 children)**;
median ionized 1.19 mmol/L.

## Result 1 — age-banded albumin coefficient (total Ca ~ ionized + albumin), mg/dL per g/dL
| age band | n | albumin coef [95% CI] | vs adult 0.8 |
|---|---|---|---|
| <1mo   | 4,169 | 0.815 [0.766, 0.864] | ~0.8 |
| 1–12mo | 8,936 | 0.802 [0.779, 0.826] | ~0.8 |
| **1–3yr**  | 4,206 | **0.929 [0.902, 0.956]** | **under-corrected by 0.8** |
| 3–12yr | 5,769 | 0.853 [0.829, 0.876] | under-corrected by 0.8 |
| >12yr  | 900   | 0.721 [0.661, 0.781] | over (→ adult) |
| OVERALL| 23,980| 0.763 [0.749, 0.777] | |

Age-dependence is real and replicates ledger 12d (inverted-U, peak in toddlers). **Correction to prior claim:**
the under-correction is in TODDLERS/school-age (1–12yr), NOT neonates/infants (whose coef is ~0.8). The earlier
"adult 0.8 under-corrects in infants" statement was imprecise — it's a toddler phenomenon.

## Result 2 — reclassification vs ionized truth (the intended headline): WASHES OUT
Ionized bands hypo<1.15 / norm / hyper>1.35 mmol/L; corrected-Ca bands 8.5/10.5 mg/dL.

| band | n | %miss raw | %miss Payne-0.8 | %miss age-corr | Payne→age-corr |
|---|---|---|---|---|---|
| <1mo   | 4,169 | 42.4 | 46.1 | 46.2 | fixes 7 / breaks 10 |
| 1–12mo | 8,936 | 37.2 | 32.3 | 32.3 | fixes 2 / breaks 4 |
| 1–3yr  | 4,206 | 33.9 | 31.1 | 32.3 | fixes 23 / **breaks 70** |
| 3–12yr | 5,769 | 38.8 | 37.2 | 37.6 | fixes 22 / breaks 44 |
| >12yr  | 900   | 42.2 | 48.7 | 47.9 | fixes 20 / breaks 13 |
| ALL    | 23,980| 38.1 | 36.3 | 36.6 | fixes 74 / **breaks 141 (net −67)** |

The age-corrected formula is **no better — slightly worse** — than adult Payne everywhere. Even where the
coefficient differs most (1–3yr), age-correction breaks more than it fixes.

## Result 3 — why it washes out (calibration to ionized, r): the surrogate is weak
| band | r(raw, ion) | r(Payne, ion) | r(age-corr, ion) |
|---|---|---|---|
| ALL | +0.467 | +0.488 | +0.485 |

Albumin-corrected calcium tracks ionized only at r≈0.47–0.49 — barely above raw total, and age-correction adds
nothing over Payne. Refining the slope cannot help a surrogate that fundamentally doesn't track the ground truth.
(Absolute misclassification ~36% is partly threshold-mismatch, but the RELATIVE null — age-corr ≈ Payne — is
threshold-independent, driven by the calibration ceiling in Result 3.)

## Honest bottom line
- The age-dependent binding slope is a real, minor measurement observation (confirmatory; toddlers peak ~0.93).
- The clinically-useful extension (age-corrected formula → better classification) **FAILS**: corrected calcium is
  a poor surrogate for ionized calcium in critically ill children regardless of correction factor. The message is
  "measure ionized directly," not "use a better correction" — the same conclusion the whole measurement-bias seam
  keeps returning. Likely also confirmatory vs existing pediatric-ICU literature on corrected-Ca inferiority.
- **Not a publishable standalone win.** The flagship's adult globulin story is unaffected (different mechanism:
  globulin OVER-correction in adults with a race gradient; pediatric here is albumin-slope calibration).

## Files
- `scratchpad/pic_ca_analysis.py`, `scratchpad/labs_ca_alb.csv`, `scratchpad/pic_paired_ca_alb.csv`.
