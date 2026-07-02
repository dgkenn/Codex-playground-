# Potassium cross-method IV — the negative-control gate RETIRES it (hemolysis contaminates the discordance)

The electrolyte-repletion de-implementation target (reflexive KCl for mild hypokalemia). Applies the same
cross-method assay-noise design that worked for Hb and glucose — and is the first analyte where it **fails a
validity gate**, honestly and for a mechanistic reason.

## Design
Chemistry K (50971, `lab_k`) vs blood-gas K (50822, `lab_kbg`) within 1h → nominal same-blood analytic
discordance, σ = 0.395 mEq/L (n=25,904 pairs). Z = 1(K < 3.5); D = KCl repletion (inputevents 225166) ≤6h;
control = the other-method K (quadratic around 3.5); Y = in-hospital / 30-day mortality. Negative control:
does the K-flag predict **RBC transfusion** — a treatment potassium cannot trigger?

## Step 1 — the acted-upon-measurement direction replicates (3rd analyte)
| instrument side | control | first stage (FS, F) | verdict |
|---|---|---|---|
| Z = blood-gas flag | chemistry | −0.10 (F 42–52), WRONG-SIGNED | invalid — ABG K not the acted-upon value |
| Z = **chemistry flag** | blood-gas | **+0.14 (F 59–64)**, correctly signed | clinicians replete off the BMP potassium |

The glucose lesson (build the instrument on the measurement the clinician acts on) reproduces on potassium:
the chem-flag direction has a correctly-signed, strong first stage; the ABG-flag direction is wrong-signed.

## Step 2 — the negative control FIRES → retire the instrument
Valid (chem-flag) direction:

| cohort | n | flag-ITT [95% CI] | balAge | **NC: K-flag → RBC** |
|---|---|---|---|---|
| all, in-hospital | 10,596 | −0.018 [−0.042, +0.005] | +0.99 | **+0.026 (p<0.05) !!** |
| ICU, 30-day | 7,997 | −0.042 [−0.072, −0.012] | +1.01 | **+0.027 (p<0.05) !!** |
| all (wider band), in-hosp | 13,979 | −0.012 [−0.035, +0.011] | +0.80 | **+0.028 (p<0.05) !!** |
| ICU, 30-day (wider) | 10,550 | −0.032 [−0.060, −0.004] | +0.80 | **+0.031 (p<0.05) !!** |

Being flagged hypokalemic raises the RBC-transfusion rate by ~2.7 pp — but potassium level does **not**
indicate transfusion. So the K-flag carries information beyond potassium: the exclusion restriction is
violated. **Age balance passed (~+1 yr) while the NC failed** — the canonical case where balance alone would
have certified a confounded instrument. The borderline ICU-30day "protective" −0.042 is therefore **not
claimable**; it is confounded, not causal.

## Mechanism — why potassium discordance is not clean analytic noise (unlike Hb)
**Hemolysis.** A hemolyzed specimen releases intracellular K and reads **falsely high**; the chem-vs-ABG
discordance is then driven partly by which sample hemolyzed, not by analytic imprecision. Hemolysis tracks
difficult draws, sicker patients, and more downstream intervention (incl. transfusion) — so the "noise" is
correlated with acuity and outcome. The cross-method assumption (same blood → discordance is pure analytic)
holds for Hb (co-oximetry vs impedance both measure intact hemoglobin) but **breaks for potassium** because
one failure mode (hemolysis) perturbs the two assays' inputs differently and non-randomly.

## Verdict
The cross-method assay-noise IV does **not** universally apply. For potassium it is **retired by the negative
control** (hemolysis-contaminated discordance), even though the first-stage sign and age balance both looked
fine. This is the toolkit behaving correctly: a mandatory NC gate that catches a confounded instrument the
balance gate misses. It also sharpens the scope rule — cross-method discordance is clean only when the two
assays share the same physical measurand and failure modes (Hb ✓, glucose ✓ once acted-upon side chosen,
potassium ✗ via hemolysis). De-implementation question (does reflexive K repletion change mortality?) remains
**unanswered by this instrument**; a hemolysis-screened or provider-preference design would be required.
