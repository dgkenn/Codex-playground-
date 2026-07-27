# The arterial-line decision aid — FINAL (honest, adversarially-reviewed) version

**Supersedes** doc 21's AUC claims. Pre-specified in doc 22. **This version incorporates a full adversarial
peer-review pass (§5) and reaches a different, harder conclusion than doc 21: a standalone pre-operative
risk-*prediction* tool does NOT survive review. What survives — and is genuinely high-impact — is the C8
measurement finding plus a MODEL-FREE actionable translation.** Benefit is reserved for the trial (doc 24).

## 1. The honest bottom line (read this first)
- **C8 (the measurement finding) is the contribution** and it is solid + externally validated: the oscillometric
  cuff misses ~half of arterial-defined intraoperative hypotension (device physics), this attenuates the measured
  hypotension→harm association, and a treatment gap (OR 1.34) links it to worse care. Replicated in eICU
  (154 US hospitals).
- **A pre-operative risk *score* for who-needs-a-line does not work well and must not be sold as validated.** On
  a rigorous, leakage-free, held-out analysis its discrimination is ~**0.57** (barely above chance), it **failed
  external validation** (VitalDB AUC 0.546, non-monotone calibration), it is **structurally derived on the wrong
  population** (only already-lined patients), and its apparent "harm" signal is **generic severity**, not the
  cuff-blindness pathway.
- **What IS actionable from C8 — without any prediction model:** (a) a **guideline-anchored structural aid**
  (auto-place for established indications; place for a specific benefit); and (b) a **detection correction**
  (cuff cycled ≤2–3 min + treat at MAP<70) that recovers sensitivity from 57%→75% and needs no model at all. The
  gray-zone severity factors (age, ASA, major surgery, anticipated duration) are retained only as an
  **exploratory, hypothesis-generating** risk cue with all caveats stated.

## 2. The aid (what to actually recommend)
- **Layer 1 — auto-place (established guideline indication; not a model):** cardiac / major-vascular / neuro /
  interventional cases and ASA ≥ 4. (Revealed practice corroborates these are already near-universal: 97/95/91%
  and 89–94% — i.e. no decision support is needed here; this layer *codifies*, it does not predict.)
- **Layer 2 — place for a specific established benefit (any one; not a model):** beat-to-beat control · frequent
  ABG/serial labs · NIBP unreliable · active vasoactive titration · dynamic goal-directed monitoring.
- **Layer 3 — gray zone (no Layer-1/2 trigger):** the actionable, evidence-backed step is the **detection
  correction** — cuff cycled ≤ 2–3 min and treated at **MAP < 70** (C8: recovers most missed hypotension, no
  model needed). Higher-acuity features (older age, ASA≥III, major abdominal/urologic surgery, longer
  anticipated case) may *raise the index of suspicion* for direct arterial monitoring, but this is presented as
  **exploratory** — see §3/§4 for why it is not a validated predictor.

## 3. Why the pre-op score is only exploratory (the killing analyses)
INSPIRE co-recording cohort, n=27,528, 25,080 subjects; subject-level 70/30 split; frozen score, held-out test.
| Problem | Analysis | Result |
|---|---|---|
| **Realized-duration leakage** | drop realized duration (a look-ahead: long cases run long *because* of intraop events) | Y_missed AUC 0.609→**0.574**; **Y_harm 0.682→0.572** — nearly all the Y_harm "signal" was leakage |
| **Failed external validation** | frozen score on VitalDB (n=1,071) | AUC **0.546 [0.511–0.579]**; calibration **non-monotone** (24/31/36/35/25%) — a failed validation, not "attenuation" |
| **Severity confound (not the mechanism)** | score→harm within Y_missed=1 vs Y_missed=0 | harm\|missed=0 AUC **0.708** > harm\|missed=1 **0.646** — the score predicts general harm *better* in patients WITHOUT cuff-missed hypotension → it is a sick-big-surgery marker, not a cuff-blindness marker |
| **Verification/selection bias** | lined (derivation) vs un-lined (deployment) population | lined ASA≥3 13% vs 9%, dept-mix shifted (neurosurgery 23% vs absent); the target outcome is only observable in already-lined patients, so the deployment population is *categorically* unrepresented |
| **Discrimination ceiling** | +baseline creatinine | +0.001 — consistent with (not proof of) the known ~0.6 ceiling for pre-op prediction of an intraoperatively-determined event |

**Conclusion:** leakage-free, externally, and mechanism-specifically, the pre-op score is ≈0.55–0.57 — not a
usable predictor. The earlier 0.75 was in-sample, leaky (realized duration), and on a severity-confounded target.

## 3b. Safety of the detection correction (MAP<70) — is it overtreatment? (VitalDB, 5,906 artifact-hardened pairs)
The one action we DO recommend must be shown safe, not just sensitive. Confusion vs the arterial reference:
| cuff threshold | sensitivity (art<65) | specificity | false-positive rate | PPV | readings flagged |
|---|---|---|---|---|---|
| < 65 (guideline) | 56.1% | 89.8% | 10.2% | 49.8% | 17.2% |
| **< 70 (correction)** | **71.9%** | 81.2% | **18.8%** | 40.7% | 26.9% |
| < 75 | 80.2% | 69.9% | 30.1% | 32.4% | 37.7% |

- Moving <65→<70 buys **+15.8 points of sensitivity** for **+8.6 points of false-positive rate** (≈1.8 true
  catches per extra false alarm).
- **The overtreatment concern is bounded:** the readings newly flagged by the <70 rule (cuff 65–70) have
  **median arterial MAP 70** and are truly <65 in only 24.7% — i.e. the correction intensifies attention in
  *mildly low-normal* patients, not toward iatrogenic hypertension. Treating a true-MAP≈70 patient toward target
  is low-risk; the asymmetry (missed hypotension → AKI/mortality OR ~2 vs brief treatment of a MAP-70 patient)
  favors the correction. The definitive net-harm answer is the RCT's third (MAP<70, model-free) arm.
- **Honest cost:** at <70, PPV is 41% — a majority of alarms are in true-MAP≥65 patients, so the correction
  trades specificity for sensitivity. Reported, not hidden; the trade is defensible but should be clinician- and
  context-adjustable (e.g. higher threshold only where hypotension risk is elevated).

## 4. What honestly survives (and why it's still worth publishing)
- The **measurement finding (C8)** — high-impact, externally validated, mechanism-anchored.
- The **detection correction** (cuff cycling + MAP<70) — model-free, directly supported (57%→75% sensitivity),
  immediately actionable, and it is the honest answer to "what do I do in the gray zone" when a line isn't placed.
- The **structural aid** (Layers 1–2) — guideline-based codification; useful for training/consistency, not a
  novel predictor.
- The gray-zone severity cue as **explicitly exploratory**, motivating the prospective trial (doc 24), which is
  the only design that can (i) enroll the true un-lined gray-zone population, (ii) randomize to break
  confounding-by-indication, and (iii) use anticipated (not realized) duration.

## 5. Adversarial review & response ledger (hostile senior reviewer: anesthesiologist + biostatistician)
| # | Attack (severity) | Response / action taken |
|---|---|---|
| 1 | External validation collapsed to near-chance; non-monotone calibration (**FATAL**) | **Accepted.** Reported as a **failed** external validation (§3), not explained away; standalone-tool framing withdrawn. |
| 2 | Realized-duration leakage; duration does most of the work (**FATAL**) | **Confirmed by analysis** (Y_harm 0.68→0.57 without duration); duration demoted; honest AUC is leakage-free ~0.57; trial will use anticipated duration. |
| 3 | Trained/tested only on already-lined patients ≠ deployment population (**FATAL, unfixable in data**) | **Accepted as the deepest flaw** (§3). Only a prospective trial in un-lined gray-zone patients resolves it (doc 24). Selection characterized (Table, §3). |
| 4 | DCA implies causal action while disclaiming causality; threshold not anchored to real a-line harm (**MAJOR**) | **Accepted.** DCA demoted; net benefit reframed as prediction-task-only, contingent on unproven action-benefit; threshold must be anchored to cited complication rates in any future report. |
| 5 | Y_harm composite = general severity, not the cuff-blindness pathway (**MAJOR**) | **Confirmed** (harm\|missed=0 0.708 > harm\|missed=1 0.646). Y_harm withdrawn as evidence the score captures the mechanism. |
| 6 | Model menu without pre-specified primary (**MINOR-MOD**) | **Fixed.** Primary = equal-weight count (the operationalized rule); all else are sensitivity analyses (per SAP doc 22). |
| 7 | Layers 1–2 just formalize reflexive practice (**MINOR**) | **Accepted.** Stated explicitly: Layers 1–2 codify, they don't predict; the only "prediction" claim (Layer 3) is demoted to exploratory. |
| — | Over-claims (49% sensitivity ≈ coin-flip; "ceiling confirmed"; trivial Brier gain; no gestalt comparator) | **All softened/removed** in this version; "confirmed"→"consistent with"; in-sample calibration no longer offered as if it were external. |

**Reviewer verdict adopted:** fold into the C8 measurement paper as a **hypothesis-generating clinical-implications
section** (not a standalone validated tool), with the detection correction as the concrete deliverable and the
trial (doc 24) as the path to a benefit-validated instrument. This is the version that survives review — by not
over-claiming.

## 6. SECOND adversarial round (fresh reviewer: anesthesiologist + trials methodologist) — verdict + responses
**Verdict: MAJOR REVISIONS, not reject** — the RTM-safe design and the score demotion are recognized as genuine
upgrades; the measurement finding (C8) is publishable. Remaining attacks on the *surviving* claims, each with the
analysis run to neutralize it:

| # | Attack (severity) | Analysis run / response |
|---|---|---|
| 1 | MAP<70 correction is in-sample; net benefit asserted; ~doubling false alarms → vasopressor overtreatment (**FATAL if unfixed**) | **External replication of the specific threshold numbers:** eICU (1,140,999 paired readings, 154 US hospitals) reproduces VitalDB almost exactly — sensitivity <65→<70 = 53.0%→70.7% (VitalDB 56.1%→71.9%), FPR 11.8%→23.6% (VitalDB 10.2%→18.8%). **Overtreatment bounded** (§3b): newly-flagged readings have median arterial MAP **70** (only 25% truly <65) — intensifies attention in mildly-low-normal patients, not toward hypertension. **Reframed** as the RCT's (co-primary) hypothesis, not a guideline change. |
| 2 | Harm-attenuation may be tautological — cuff-detected is definitionally a milder subset (**MAJOR**) | **Tautology test (INSPIRE n=27,528):** with continuous true arterial severity (burden+depth) in the model, **cuff-hypotension OR → 1.05 [0.98–1.12], null**, while arterial burden OR 1.73 carries all signal. This is **not a rebuttal but a reframe**: the attenuation is the exact, quantified **consequence** of cuff undercounting true severity (C8) — not an independent "measurement causes harm" claim. Presented that way it is airtight; cuff carries zero harm information beyond being a noisy proxy for arterial burden. |
| 3 | Residual RTM/artifact; "device physics" not shown; position/vasopressor/device confounders (**MAJOR**) | Systematic over-read shown as Bland-Altman-by-stratum (bias +30.6 mmHg at arterial 20–55 → ~0 mid-range; eICU +13.1→+5.2→~0) — widening positive bias as MAP falls = systematic, not random. **Window-width/anchor sensitivity RUN (VitalDB, ±30/60/90 s): sensitivity 55.0/56.1/55.9% at <65, bias +30.7/+30.8/+30.5 — rock-stable, not a timing artifact.** **Vasopressor confounder RULED OUT two ways (INSPIRE):** (a) between-patient — OFF any vasoactive infusion the low-pressure over-read is +17.9 mmHg (≥ the +9.9 ON-infusion); (b) **within-patient MAP-matched crossover (the design reviewers credit): at matched true MAP within the same operation, the on-vs-off bias difference is −0.1 mmHg [−2.8,+2.6] (art 20–55) and +0.3 [−1.7,+2.2] (55–65) — null.** Infusion adds no cuff error beyond low pressure itself → device physics, not vasoconstriction. Device heterogeneity limited (VitalDB = single Solar8000 family; eICU's multi-device population still replicates). Position not in current data (stated limitation → trial captures it). |
| 4 | RCT tension: why an invasive a-line trial not a cheaper cuff-threshold trial? Power needs clustering (**MAJOR**) | Doc 24 updated: the **cuff-cycling + MAP<70 arm promoted toward co-primary / faster lead-in** (cheaper, non-invasive, tests the most actionable question first); power calculation to carry the site **ICC/design-effect**, with a sensitivity table across effect sizes. |
| 5 | "Worse INPRESS" risk (**MODERATE**) | Explicit contrast table added (doc 24 §6): INPRESS varied the BP *target* in already-lined patients; this trial varies the *monitoring modality / line decision* at a fixed target in un-lined gray-zone patients. |
| 6 | eICU = replication of *direction*, not *mechanism* (**MINOR**) | Wording corrected throughout: eICU externally validates the **direction and approximate magnitude** of cuff undercount, not the specific device-physics pathway (ICU cuff error has other contributors: edema, arrhythmia, obesity). |

## 7. THIRD adversarial round (convergence check) — verdict + closure
**Verdict: CONVERGED.** Severity trajectory: round 1 = FATAL (things that were *wrong* — a leaking non-validating
score, causal language for a measurement artifact); round 2 = MAJOR (fixable); **round 3 = "a completeness gap,
not a validity gap … close to publishable, should clear a top journal."** The single remaining item — the
vasopressor mechanism analysis — was flagged as needing the stronger *within-patient crossover* design; that is
now RUN (above, §5 row 3: null at matched MAP) and the mechanistic attribution (device physics) is resolved.
Two honesty fixes round 3 required, both applied:
- **Magnitude, not just direction, stated honestly:** the over-read is +30.6 mmHg (VitalDB, intraop, 2-s
  waveforms) vs +13.1 mmHg (eICU, ICU, minute-ish, sicker/edematous population) — ~2.3×. We report this as
  **replication of direction and order-of-magnitude**, not identical magnitude; the gap is expected from the
  cohort/granularity/acuity differences and is not glossed as tight replication.
- Single-monitor (Solar8000) / single-institution for the primary cohort is disclosed; eICU (multi-device, US)
  provides the cross-setting check.

**Net:** after three rounds, the durable, review-surviving package is (i) the **C8 measurement finding** (RTM-safe,
Bland-Altman-by-stratum, eICU-replicated); (ii) the **harm-attenuation reframed as C8's quantified consequence**
(tautology test: cuff adds nothing beyond true burden); (iii) the **MAP<70 detection correction** with
externally-replicated operating characteristics and a bounded, honestly-reported overtreatment cost, **explicitly
a trial hypothesis**; (iv) the **RCT (doc 24)** as the only benefit-validating design. The predictive score
remains exploratory. No claim in this list depends on an un-replicated or in-sample number.
