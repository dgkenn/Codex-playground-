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

## Instrument C — attending-rotation time-RDD: FAILED on real data → RETIRED (in MIMIC)
| drug | n | FS | RF(mort) | LATE |
|---|---|---|---|---|
| ppi | 11,010 | +0.83 | +0.218 | +0.264 |
| opioid | 16,748 | +0.99 | −0.625 | −0.630 |
| benzo | 7,234 | +0.85 | +0.087 | +0.103 |

**Nonsensical LATEs** (−0.63, +0.26 on a mortality scale). Root cause: the design instrumented on the receiving
service's continuation propensity at a **transfer**, but transfers in MIMIC are **clinically triggered** (move to
ICU on deterioration, to the floor on improvement) → the "handoff" is NOT exogenous to the patient's trajectory;
the transfer *is* the confounder. It also lacked a balance gate. **This cannot be salvaged in MIMIC** — a valid
attending-rotation RDD needs explicit *scheduled* attending-rotation timestamps (same unit, new attending, on a
roster) that MIMIC does not track. **Retired**; flagged as a design that would need a dataset with attending
schedules (some health-system EHRs have this).

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
