# Pivot ideas: treatment TIMING / SEQUENCE / decision-order on MIMIC-IV (+ eICU-CRD)

Status: idea-generation only, NOT committed. Domain: critical care medicine /
anesthesiology tier. Constraint enforced throughout: no candidate may map onto
an already-named index/score (VIS, VDI, BPRI, SOFA, shock index, lactate
clearance, time-to-antibiotics) or a known dose→outcome relationship. The
construct itself — not just the dataset application — must be unnamed in the
literature. Novelty checked via PubMed (`mcp__...__search_articles` /
`get_article_metadata`); queries and verdicts are reported per idea below so
the search trail is auditable. All causal timing/sequence claims from
observational EHR data are confounded by indication and vulnerable to
immortal-time bias — this is flagged per idea with a concrete mitigation, not
papered over.

---

## Idea 1 (TOP RANK): Order of liberation from multi-modality organ support — "de-escalation sequence" as a novel construct

**Precise question.** Among ICU patients who simultaneously receive ≥2 of
{invasive mechanical ventilation (IMV), vasopressors, CRRT/IHD}, does the
**order** in which these supports are withdrawn (e.g., extubate-while-still-
pressor-dependent vs. pressor-off-then-extubate vs. RRT-off-before-vasopressor-
off vs. the reverse) predict a composite of reintubation/re-initiation of
support, ICU readmission, or mortality — independent of severity at the time
each withdrawal decision is made?

**The novel construct.** Not "time to liberation" (a duration, already well
studied) and not any single pairwise de-escalation (see novelty check below —
the MV/vasopressor pair specifically is already published). The novel object
is the **liberation ORDER across ≥3 concurrently-held organ supports**,
encoded as a permutation/partial-order per patient (e.g., RRT→vasopressor→MV
vs. vasopressor→RRT→MV vs. simultaneous), and tested as a categorical
predictor. No existing named index summarizes "which organ support comes off
first" across three modalities; this is a structural/sequence variable, not a
dose or a duration.

**PubMed novelty check.**
- `extubation before vasopressor discontinuation ICU outcome` → 3 hits, of
  which **Zarrabian et al., Am J Respir Crit Care Med 2022** ("Liberation from
  Invasive Mechanical Ventilation with Continued Receipt of Vasopressor
  Infusions," PMID 35107416, [DOI](https://doi.org/10.1164/rccm.202108-2004OC))
  is a **direct collision** with the MV-before-vasopressor binary question
  (Calgary cohort, n=6,140; extubation on high-dose pressors → higher
  reintubation risk). **This specific pairwise framing is DONE — do not
  resubmit it.**
- `renal replacement therapy discontinuation while still receiving
  vasopressors timing outcome` → 0 hits.
- `weaning order vasopressors sedation mechanical ventilation which
  discontinued first ICU` → 0 hits.
- `first organ support modality added sequence triple organ failure ICU
  mortality MIMIC` → 0 hits.
- `simultaneous versus staggered organ support escalation MIMIC ICU machine
  learning` → 0 hits.
- **Verdict:** the 2-way MV↔vasopressor liberation-order question is
  published and must be excluded. The generalization to **3-way order
  (MV, vasopressor, RRT, and optionally sedation/NMB) treated as a sequence/
  permutation construct**, and the symmetric **escalation-order** question
  (which support is *added* first as multi-organ failure evolves, not just
  which comes *off* first) both returned zero hits and are not addressed by
  Zarrabian or by the SETS/"sequential extracorporeal therapy" literature
  (De Rosa et al. 2023, PMID 37290408, [DOI](https://doi.org/10.1159/000527573)),
  which is a clinical-protocol proposal for combining blood-purification
  modalities, not an outcome study of observed real-world liberation order.

**Feasibility on MIMIC-IV.**
- IMV start/stop: `procedureevents` (itemid family for "Invasive Ventilation"
  start/end, or derive from `chartevents` ventilator-mode entries / the
  community `ventilation_durations` concept table in mimic-code).
- Vasopressor start/stop: `inputevents` for norepinephrine, epinephrine,
  vasopressin, phenylephrine, dopamine itemids; define "on vasopressor" as any
  active infusion interval; merge contiguous/overlapping infusions per agent
  and across agents into a single "vasopressor-on" interval per patient.
- CRRT/IHD start/stop: `procedureevents` CRRT itemids (and `chartevents` for
  IHD session flags); mimic-code's `crrt` concept table is a direct starting
  point.
- Cohort: adult ICU stays with ≥2 of the 3 supports overlapping at any point
  (estimate low-to-mid thousands in MIMIC-IV given ~50-60k ICU stays and
  typical multi-organ-failure prevalence of 10-20%; eICU-CRD can serve as an
  external replication cohort using the `infusiondrug`, `respiratoryCare`,
  and `treatment` tables, though eICU's coarser vasopressor/RRT timestamping
  will need sensitivity analysis).
- **Confounding/immortal-time risk:** severe — sicker patients both keep
  support on longer AND get supports removed in a different order because
  clinicians are reacting to evolving illness, not randomizing order. Order
  is fundamentally entangled with severity trajectory (classic confounding by
  indication, compounded because the "exposure" — order — is only fully
  defined after all withdrawals have happened, i.e., look-ahead bias).
  **Mitigation:** (a) landmark analysis — fix a landmark time (e.g., once all
  ≥2 supports have been concurrently active for ≥24h), define order only by
  what is observed to happen *after* the landmark, and exclude/sensitivity-
  analyze patients who die or are dischargedbefore any withdrawal (immortal-
  time-safe by construction); (b) treat order as a time-varying multi-state
  model (Markov/competing-risks states = which subset of supports remain
  active) rather than a single fixed categorical exposure, so the "exposure"
  is always defined prospectively from the landmark; (c) adjust for
  the most recent SOFA/vasopressor dose/P:F ratio at the landmark and at each
  state transition as time-varying covariates (marginal structural model /
  target-trial emulation: each withdrawal decision is one "trial" with the
  alternative being "did not withdraw this support at this time").

**Impact tier + biggest threat.** Critical Care Medicine / Intensive Care
Medicine tier (B+/A- journal, e.g., Crit Care Med, ICM, CCExplorations) if
multi-state modeling is done rigorously; this is a natural follow-on / clear
generalization of Zarrabian 2022 and reviewers will expect that paper cited
and explicitly differentiated. **Biggest threat:** reviewers may see this as
"just Zarrabian + RRT" unless the multi-state/3-way framing and the
escalation-order (not just de-escalation-order) angle are foregrounded as the
genuinely new piece; also, RRT discontinuation decisions are heavily protocol-
driven (urine output, fluid balance) in ways MV/vasopressor decisions are not,
so the three supports may not be exchangeable in a single model — needs
modality-pair-specific sensitivity analyses, not just one omnibus order
variable.

---

## Idea 2: Escalation-order at the moment of shock recognition — does the FIRST organ support added (rather than which drug/dose) predict trajectory?

**Precise question.** At the moment a patient first meets multi-organ-
dysfunction criteria (e.g., simultaneous new vasopressor need + new severe
hypoxemia + rising creatinine within a 6h window), clinicians do not start
all indicated supports simultaneously — one is started first. Does the
**identity of the first-added support** (vasopressor-first vs. IMV-first vs.
RRT-first, when ≥2 are equally "due" by objective criteria at that window)
predict 30-day mortality or organ-failure-free days, after matching/
adjusting for which organs were how dysfunctional at that moment?

**The novel construct.** "Which lever does the bedside team pull first when
several are simultaneously indicated" — a decision-order variable at the
moment of clinical equipoise, not a severity score and not a known triage
algorithm. Distinct from Idea 1 (which is about withdrawal order over the
whole stay); this is specifically about the **initial escalation decision**.

**PubMed novelty check.**
- `order of organ support initiation septic shock outcome` → 11 hits, none of
  which study observed real-world initiation ORDER as the exposure; results
  were dominated by sepsis-bundle/order-set adherence studies (e.g., Dale et
  al. 2023, PMID 37206374, [DOI](https://doi.org/10.1097/CCE.0000000000000918),
  which studies whether a sepsis *order set* — a checklist — was used, an
  unrelated meaning of "order") and a SETS review (PMID 37290408) proposing a
  sequence of extracorporeal therapies prescriptively, not testing observed
  order as a predictor.
- `first organ support modality added sequence triple organ failure ICU
  mortality MIMIC` → 0 hits (shared with Idea 1).
- **Verdict: clean.** No existing study isolates "which support was started
  first at simultaneous-indication onset" as the exposure of interest.

**Feasibility on MIMIC-IV/eICU.** Same source tables as Idea 1
(`inputevents`, `procedureevents`), plus labs/vitals (`labevents`,
`chartevents`) to construct the simultaneous-indication window (e.g., a
6-12h window in which a vasopressor-dose threshold, a P:F-ratio threshold,
and a creatinine/urine-output threshold are all crossed). The harder part is
*defining* "equally indicated" objectively and pre-specifying it before
looking at what was actually done — this needs the indication criteria fixed
first (e.g., literal KDIGO/Berlin/Surviving-Sepsis thresholds) and the order
extracted only afterward, otherwise indication and order become circular.
Cohort size likely smaller than Idea 1 (requires the tight simultaneous-onset
window), plausibly low hundreds to ~1-2k in MIMIC-IV alone — eICU-CRD
external replication is more important here than for Idea 1.

**Confounding/immortal-time risk.** Severe and harder to fully resolve than
Idea 1: a clinician choosing vasopressors-first over intubation-first is
very plausibly choosing based on something not in the EHR (mental status,
work of breathing trend, gestalt) — confounding by indication that is not
fully measurable. Target-trial emulation framing helps discipline the
analysis (define the trial as "among patients meeting all three thresholds
in the same window, what if we had assigned support A first") but residual
confounding cannot be fully excluded; this should be presented as hypothesis-
generating / explicitly flagged for unmeasured confounding, with falsification
tests (e.g., does first-support choice predict an outcome it has no plausible
mechanism to affect, like unrelated same-admission surgical complication
rates — if yes, that signals confounding).

**Impact tier + biggest threat.** Slightly higher conceptual novelty than
Idea 1 but smaller, harder-to-define cohort and weaker causal footing.
Tier: solid CCExplorations/ICM-Experimental-and-Translational-tier paper,
less likely top-tier Crit Care Med/ICM as a standalone. **Biggest threat:**
the indication-equipoise window definition is a judgment call that reviewers
will attack as post-hoc-tunable; pre-registration of the exact thresholds
(consistent with this repo's general preference for pre-specified,
config-driven definitions) is close to mandatory for credibility.

---

## Idea 3: Relative order of nutrition initiation vs. vasopressor-dose trajectory direction (escalating vs. de-escalating) at the time enteral feeds start

**Precise question.** Among vasopressor-dependent ICU patients, does
initiating enteral nutrition while the vasopressor dose is still
**rising/unstable** (vs. waiting until the dose trajectory has turned to
**falling/stable**) predict GI complications or mortality differently than
dose magnitude alone would predict — i.e., is the *direction of the
hemodynamic trend at the moment of the feeding decision* (not the dose
itself, which is the already-studied piece, cf. VIS-style indices) an
independent signal?

**The novel construct.** Trend-direction-at-decision-time (rising vs. falling
vasopressor dose when a co-indicated but logistically deferrable therapy —
enteral feeding — is started), as distinct from dose magnitude (which is the
basis of all existing vasopressor-intensity indices and is explicitly
excluded by the prompt's "already-named index" rule).

**PubMed novelty check.**
- `enteral nutrition initiation relative timing vasopressor escalation
  shock` → 0 hits.
- General background: early-vs-late enteral nutrition in shock (e.g.,
  NUTRIREA-2-era literature) is a well-studied *duration/timing-from-
  admission* question, but searches specifically combining nutrition timing
  with vasopressor-trend-direction (rising vs. falling, not just "on
  vasopressors yes/no") returned nothing.
- **Verdict: clean on the trend-direction framing,** but adjacent
  early-vs-late-EN-in-shock literature is large and well-developed (NUTRIREA-2
  and follow-ups) — this idea must be framed strictly as "trend direction at
  decision time," not "early vs. late," to avoid simply re-deriving the known
  literature under a new name.

**Feasibility on MIMIC-IV.** `inputevents` for vasopressor dose
time series (compute local slope via a short rolling window, e.g., dose
change over preceding 4-6h, at the timestamp enteral nutrition orders begin
in `inputevents`/`procedureevents`/nutrition-related itemids); GI
complication outcomes from `chartevents`/`diagnoses_icd` (ileus, bowel
ischemia codes) are comparatively rare events in MIMIC-IV alone — likely
underpowered without eICU pooling, and eICU's nutrition documentation is
less granular than MIMIC-IV's, which is a real feasibility risk specific to
this idea.

**Confounding/immortal-time risk.** Moderate-severe: feeding-while-escalating
is itself a marker that the clinical team judged the patient stable enough
to tolerate feeds despite rising pressors, so the decision encodes
unmeasured clinical judgment about gut perfusion. Landmark/sequential target-
trial emulation at each dose-change timestep is feasible but the outcome
(GI complications) is rare enough that statistical power, not bias, may be
the dominant problem.

**Impact tier + biggest threat.** Lower impact tier than Ideas 1-2 (likely a
secondary/derived-cohort paper, not primary CCM/ICM) because of the power
problem and because it sits adjacent to a very mature EN-timing literature
that reviewers will reflexively (if not entirely correctly) pattern-match
this against. **Biggest threat:** rare-outcome underpowering; would need
eICU pooling or a composite/surrogate outcome (e.g., feeding intolerance
flags) to be adequately powered, which dilutes the novelty story.

---

## Idea 4: Paralytic-before-sedative vs. sedative-before-paralytic induction order at intubation, and downstream delirium/awareness risk

**Precise question.** At the moment of intubation in the ICU (not the OR),
does the **order** in which induction-adjacent sedative and neuromuscular
blocking agents are administered (paralytic given before adequate sedation
is established, vs. the reverse, vs. simultaneous) — extractable from
`inputevents` start-times at second/minute resolution — predict downstream
ICU delirium (CAM-ICU positive days) or post-traumatic-stress/awareness-
adjacent proxies, independent of total doses given?

**The novel construct.** Induction *sequencing* at single-event granularity
(minutes), as opposed to the well-studied RSI-protocol-adherence or drug-
*choice* literature (etomidate vs. ketamine, etc.).

**PubMed novelty check.**
- `paralytic before sedative induction order intubation ICU outcome` →
  0 hits.
- **Verdict: clean,** but feasibility is the binding constraint (see below) —
  this is the weakest idea of the set on practical grounds even though it is
  PubMed-clean.

**Feasibility on MIMIC-IV.** This is the weak link: MIMIC-IV's `inputevents`
timestamps for bolus/push doses of induction agents are frequently rounded to
the nearest documented charting time (often 5-15 min granularity in practice,
sometimes coarser), and awareness-under-paralysis is not a coded outcome in
MIMIC-IV at all — there is no reliable awareness/PTSD proxy in structured
EHR data. CAM-ICU delirium flags exist in `chartevents` and could serve as a
downstream outcome, but the causal chain from induction-order (a single
~60-second event early in a multi-week ICU stay) to delirium days later is
extremely long and confounded by everything that happens in between.
**This idea is PubMed-novel but likely not credibly answerable on MIMIC-IV
structured data** — flagging honestly rather than overselling it.

**Impact tier + biggest threat.** Low feasibility kills this even though
novelty is clean. Biggest threat: timestamp granularity and outcome-proxy
validity, not confounding per se — this would need chart-review-level
validation MIMIC-IV cannot supply at scale. Included here mainly to show the
idea was generated and explicitly ruled out, per the instruction to flag
feasibility honestly rather than silently dropping weak ideas.

---

## Ranking

1. **Idea 1 — multi-modality (≥3-way) organ-support liberation order.**
   Highest impact-to-risk ratio: PubMed-clean for the generalization (the
   2-way MV/vasopressor case is published — explicitly excluded and cited),
   strong MIMIC-IV feasibility with existing concept tables, and a tractable
   (if not fully solvable) confounding-mitigation path via landmark/multi-
   state target-trial emulation. **Top pick.**
2. **Idea 2 — escalation-order at simultaneous-indication onset.** Cleaner
   novelty than Idea 1 (no adjacent published pairwise result to carve around)
   but smaller cohort, harder-to-defend indication-equipoise window
   definition, and weaker causal footing. **Strong second pick**, especially
   as a companion/Aim-2 paper alongside Idea 1 in the same project (escalation
   order + de-escalation order = a complete "sequence of organ support over
   the full ICU course" research program).
3. Idea 3 (nutrition-timing-vs-trend-direction) — clean but likely
   underpowered on MIMIC-IV alone; needs eICU pooling.
4. Idea 4 (induction sequencing) — clean in PubMed but not credibly
   feasible on MIMIC-IV structured data; included for completeness, not
   recommended to pursue without richer (e.g., anesthesia-information-system)
   data.

All PubMed searches used `mcp__735c1792-5852-42ce-a74d-99beb6f90b6e__search_articles`
(PubMed). Per-idea zero-hit and hit results and the resulting verdicts are
recorded above; DOIs are cited inline for the two collision/adjacent papers
that matter most (Zarrabian et al. 2022, [DOI](https://doi.org/10.1164/rccm.202108-2004OC);
De Rosa et al. 2023, [DOI](https://doi.org/10.1159/000527573); Dale et al.
2023, [DOI](https://doi.org/10.1097/CCE.0000000000000918)).
