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
