# Real-data results — contraindication-gate (A, valid-but-weak) and attending-rotation RDD (C, FAILED)

## Instrument A — contraindication/indication-GATE assay-noise IV: EXOGENOUS but WEAK
| gate | n | FS (F) | ITT | balAge | read |
|---|---|---|---|---|---|
| PPI @ platelet<50k | 4,449 | +0.047 (6) | +0.054 | **+0.13** | exogenous, weak first stage |
| PPI @ INR>1.7 | 25,089 | +0.022 (6) | +0.034 | **+0.22** | exogenous, weak first stage |
| Steroid @ eos gate | 12,363 | −0.032 (24) | −0.017 | **−0.48** | exogenous; wrong-signed FS |

**Positive:** balance is excellent (balAge < 0.5 yr) — the noise-IV logic genuinely produces as-if-randomness at
a measured gate. This validates the core identification idea on a contraindication gate. **Limitation:** the
first stage is WEAK (F≈6; crossing the gate changes treatment by only 2–5 pp) → the LATE is uninterpretable
(weak-IV explosion, +1.1 to +1.6), and the reduced-form ITT cannot be cleanly attributed to the drug because the
gate lab (platelet, INR) is itself a severity signal (exclusion concern). **Verdict:** valid-but-underpowered,
same intrinsic weakness as the core assay-noise IV. Keep as a supplementary proof that the noise-IV exogeneity
holds at gates; do NOT report a treatment-effect LATE from it.

## Instrument C — attending-rotation time-RDD: RETIRED after a full salvage analysis
| drug | n | FS | RF(mort) | LATE |
|---|---|---|---|---|
| ppi | 11,010 | +0.83 | +0.218 | +0.264 |
| opioid | 16,748 | +0.99 | −0.625 | −0.630 |
| benzo | 7,234 | +0.85 | +0.087 | +0.103 |

Nonsensical LATEs (−0.63, +0.26). Level-1 cause: the design instrumented on the receiving service's propensity
at a **transfer**, but MIMIC transfers are **clinically triggered** (deteriorate → ICU; improve → floor), so the
"handoff" is endogenous — the transfer *is* the confounder.

### Salvage analysis (thought through like the nurse-PRN v1→v2 fix)
The nurse-PRN salvage worked by REFRAMING the estimand to something observable and clean (dose intensity). Can
the same be done here? I worked the candidate reframes:
1. **Isolate exogenous *same-unit* attending rotations** (calendar-driven, same care level → exogenous timing).
   Blocked in MIMIC: there is **no within-stay attending timeline**. `order_provider_id` is per-order (rotating
   residents/hours, changes constantly) — too noisy to identify a clean attending rotation. `admit_provider_id`
   is a single value per admission. So the exogenous-rotation subset is not constructible here.
2. **Restrict to lateral (same-acuity) ward→ward transfers** (bed-management/capacity driven → exogenous). Weak:
   lateral moves are often specialty-motivated too, and the drug-habit signal across same-acuity wards is small.
3. **Calendar shock (weekend/holiday deprescribing inertia).** Timing is exogenous, but the **exclusion
   restriction fails** — the "weekend effect" changes mortality through many paths (staffing, procedures,
   monitoring), not just the target drug's continuation.

### The deeper, structural reason it can't be salvaged (unlike nurse-PRN)
Even with a perfectly exogenous handoff, a **provider/team change is a BUNDLE intervention** — the new team alters
the *entire* care approach (monitoring, mobilization, consults, every drug), not just the one drug's continuation.
So the reduced form structurally cannot be attributed to the target treatment: the **exclusion restriction is
violated by construction**. This is the opposite of nurse-PRN, where the reframed treatment (dose count) cleanly
IS the exposure. It is the same reason the assay-noise IV is superior: a **lab flag triggers ~one treatment**,
whereas a **team change triggers everything**.

### And it's DOMINATED — so nothing is lost by retiring it
The attending-rotation and the provider-preference IV exploit the *same* identifying variation (provider
prescribing habit). The cross-sectional **provider-IV already works in the elective stratum** (balance passes,
recovers the MIND-USA antipsychotic null) — without needing to identify exogenous rotations and without the
extra within-patient bundle problem. The rotation version adds identification difficulty and inherits the same
provider-quality exclusion concern, with no compensating advantage. **Retire it; provider-IV covers the same
ground better.** (It could work only in a dataset with explicit attending rosters AND a passing co-intervention
exclusion test showing the rotation moves *only* the target drug — neither available in MIMIC.)

## Updated instrument scorecard (real data)
| instrument | status |
|---|---|
| Assay-noise IV (lab-flag indication) | ⏳ pending inputevents (the flagship benchmark) |
| Provider-preference IV | ✅ valid in elective/low-acuity (recovers MIND-USA antipsychotic null) |
| Nurse-PRN dose-intensity IV (v2) | ✅ salvaged, valid (opioid null; benzo/antipsy signals pending exclusion test) |
| Contraindication-gate IV (A) | 🟡 exogenous but WEAK → supplementary only |
| Attending-rotation RDD (C) | ❌ FAILED / retired in MIMIC (transfers not exogenous) |

**Reading:** two instruments work with honest scoping (provider-IV-elective, nurse-PRN-v2), one is valid-but-weak
(gate), the flagship is pending, and one failed. This is the bulletproof battery doing its job — the winners are
winners because the losers were allowed to lose. The paper reports the working instruments + the honest
retirements as part of the method's self-policing.
