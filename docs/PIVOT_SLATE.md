# Pivot slate — ranked, pre-screened candidate findings (post-vasopressor)

Synthesis of a 3-domain idea-generation + novelty/feasibility harness (PIVOT_IDEAS_{DYNAMICS,TIMING,
DISCORDANCE}.md). Constraint applied throughout: GENUINELY novel (not an already-named index/score),
feasible on accessible data (MIMIC-IV + eICU-CRD via PhysioNet; HEEDB EEG is blocked — env AWS keys are
invalid for BDSP), and must avoid the trap that made the vasopressor work incremental (a known
dose/load→outcome relationship dressed in a new conditioning).

**Novelty caveat (applies to all):** the PubMed MCP tool does literal term-matching (and was intermittently
unavailable), so "0 hits" suggests but does not prove a gap. Each pick needs one formal PubMed/Embase
vocabulary-varied pass before committing full analysis time.

## Ranked candidates

### #1 (RECOMMENDED) — Order of organ-support LIBERATION (≥3-way)
Among patients on ≥2 of {mechanical ventilation, vasopressors, CRRT}, does the ORDER in which supports
are withdrawn predict reintubation / re-escalation / mortality? Exposure = a *permutation* across
modalities, not a dose or duration.
- **Why top:** it is a genuine CLINICAL DECISION question with essentially no evidence base — the kind
  that reaches AJRCCM/CCM/ICM and avoids the "incremental risk-marker" trap that sank the vasopressor
  work (that was a marker; this is a decision). Permutation-as-exposure is a fresh construct.
- **Novelty:** the 2-way ventilation-vs-pressor version is DONE (Zarrabian, AJRCCM 2022); the **3-way +
  escalation-order** generalization is open (0 hits across formulations).
- **Feasibility:** strong — all event streams in standard MIMIC-IV tables (inputevents = vasopressors;
  procedureevents/chartevents = IMV, CRRT); eICU-CRD for replication. Cohort = multi-support patients
  (thousands).
- **Biggest threat (and the design that answers it):** confounding-by-indication + look-ahead/immortal-
  time (order is only known after the fact). MUST use a landmark / **target-trial emulation** per
  withdrawal decision + a **multi-state / competing-risks** model so exposure is always prospectively
  defined. If not handled, it collapses to "sicker patients are liberated in a different order." This is
  the standard hard-but-tractable ICU causal problem — the make-or-break is the design, not the data.

### #2 — Perturbation-response shape divergence
Within-episode SHAPE mismatch (e.g. dynamic-time-warping distance) between the HR and MAP recovery curves
after a fluid bolus or pressor taper — not either signal's own recovery magnitude/slope.
- **Novelty:** cleanest of the set (4 targeted searches, 0 hits).
- **Feasibility:** smaller, well-defined arterial-line bolus/taper cohort (~5–15k episodes); faster first
  paper; shares the streaming infrastructure.
- **Threat:** arterial-line selection; and it must be shown INCREMENTAL over admission severity and each
  signal's own magnitude-based recovery — else it reduces to "another way to detect sick patients" (the
  incremental-marker trap again). Moderate impact (a physiology-marker paper, not a decision).

### #3 — Oxygenation-proxy decoupling velocity (S/F vs P/F trajectory)
Does the continuous cheap proxy (SpO2/FiO2) keep reading "stable" while the next ABG (PaO2/FiO2) shows the
patient already crossed an ARDS severity tier — the temporal DIRECTION of S/F-vs-P/F disagreement as an
early-warning detector.
- **Novelty:** published S/F-vs-P/F work is all static calibration (Rice 2007); trajectory/decoupling-
  onset framing appears unbuilt. High-impact space (ARDS/oxygenation).
- **Feasibility:** MIMIC-IV itemids (SpO2 220277, FiO2 223835, PaO2 220224); ~10–15k ventilated/high-flow
  stays with ≥2 ABGs.
- **Threat (serious):** the ABG is drawn BECAUSE a clinician is worried — so "decoupling detected at the
  ABG" is confounded by clinical recognition itself (the proxy's failure is observed only when someone
  already acted). This endogenous-sampling confound could be fatal and must be addressed up front.

### #4 — Coupling-collapse lead time (multi-signal)
Trend in HR-MAP-RR-SpO2 coupling strength, framed as: how many hours EARLIER does the relational signal
fire than clinical recognition? Open on PubMed, high impact if real — but the threat is it reads as
"another early-warning score" unless incremental value over NEWS2/SOFA and single-signal HRV is the
headline. Higher overfitting/multiplicity risk.

## Recommendation
**Start with #1 (liberation order).** It is the only candidate that is a clinical DECISION rather than a
risk marker — the structural reason the vasopressor finding capped out incremental — and its threat
(immortal-time/confounding) is a known, tractable design problem rather than a novelty or data gap. #2 is
the best fast/clean fallback if a smaller, lower-risk first paper is preferred. #3/#4 are higher-variance.

Next step (proposed): a cheap FEASIBILITY SCOUT of #1 — confirm the multi-support cohort size and a
preliminary order→outcome signal under a landmark design — BEFORE committing to the full study and any
red-team rounds. Mirror the discipline that (correctly) bounded the vasopressor pivot early.

Cross-ref: PIVOT_IDEAS_{DYNAMICS,TIMING,DISCORDANCE}.md, VASOPRESSOR_PROJECT_FINAL.md, IDEAS_LEDGER.md.
