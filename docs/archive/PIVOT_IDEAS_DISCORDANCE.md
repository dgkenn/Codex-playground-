# Pivot ideas: monitoring DISCORDANCE / signal-disagreement on MIMIC-IV (+ eICU-CRD)

Status: idea-generation only, NOT committed. Domain: critical care medicine /
intensive care medicine / anesthesiology tier. Constraint enforced throughout:
a candidate is disqualified if (a) the two monitored signals already have a
**named** discordance/gap/gradient construct in the literature (e.g.
arterial-end-tidal CO2 gradient, core-skin temperature gradient, IBP-NIBP
agreement, ScvO2/lactate "hemodynamic incoherence", asynchrony index), or
(b) the proposed mechanism reduces to a known dose→outcome relationship with
discordance bolted on as a conditioning variable (the failure mode from the
prior "occult vasopressor dependence at normal MAP" project, where the novel
slice added only +0.03 AUC over the known VIS→mortality core). Novelty was
checked by web search (no PubMed MCP tool was available in this session —
flagged explicitly per idea) against PubMed-indexed and medRxiv literature;
queries and verdicts are reported so the trail is auditable.

**Headline finding from the novelty sweep, stated honestly up front:** the
obvious "two co-monitored ICU signals disagree → badness" pairings are almost
all already taken, several very recently (2025-2026):
IBP vs NIBP (MIMIC-IV septic cohort, n=6,060, 2024-2025), arterial-to-end-tidal
CO2 gradient (multiple 2021-2026 papers incl. a 2026 BMC Anesthesiology MIMIC
study), core-to-peripheral temperature gradient (2026 thermography papers),
capillary-refill-time vs lactate "hemodynamic incoherence" (ANDROMEDA-SHOCK
literature), ScvO2/SvO2 vs lactate, dampened arterial waveform vs cuff,
ventilator patient-triggered vs set rate (named "asynchrony index"), and —
closest of all to this brief's explicit exclusion — **oral/axillary vs
core/rectal temperature-route discordance by race delaying sepsis-bundle care**
(medRxiv, March 2025) is structurally the *same paper* as the excluded
Sjoding hidden-hypoxemia design, just with a different signal pair. A
documentation-pattern family ("Intensive Documentation Index" /
"Behavioral Telemetry", medRxiv Feb-Apr 2026, MIMIC-IV heart-failure cohort,
n=26,153) has also just claimed the "discordant care" / manual-charting-as-
signal space, including an explicit "extensive physical assessment without
cognitive assessment" discordance construct. This narrows the surviving space
considerably; the ideas below were selected specifically because they survive
this sweep, with the weakest one flagged as such rather than omitted.

---

## Idea 1 (TOP RANK): Oxygenation-proxy DECOUPLING velocity — when SpO2/FiO2 stops tracking PaO2/FiO2 *in time*, not in level

**Precise question.** Among ventilated/oxygen-supported ICU patients with
≥2 paired (SpO2,FiO2) and (PaO2,FiO2) observations within a short window,
does the **onset of temporal decoupling** between the S/F trajectory and the
P/F trajectory — i.e., S/F continuing to read stable/improving while the
*next* ABG-derived P/F has silently dropped a tier (e.g., crossing a
Berlin/Global ARDS severity boundary) — predict deterioration (escalation to
higher PEEP/FiO2, intubation if not yet intubated, prone positioning, or
24-48h mortality) beyond what either ratio's current level predicts alone?
The exposure is **directional, dynamic disagreement** (the cheap proxy says
"stable," the gold-standard sample — drawn at clinician discretion — says
"worse"), not a static calibration bias.

**The novel construct and why it is not the excluded items.** The published
S/F-vs-P/F literature (Rice 2007 derivation equation, COVID-era validation
papers, the 2026 "useful, misleading, or both?" review) is entirely about
**cross-sectional agreement/calibration**: does S/F=64+0.84×P/F hold, at what
SpO2 ceiling does the relationship saturate, can S/F substitute for P/F when
no ABG is available. None of it asks about **trajectory divergence as a
leading indicator that a clinician's pulse-ox-based "looks stable" read is
about to be falsified by the next blood gas** — i.e., the construct is a
*proxy-validity-collapse* signal, not a bias-correction factor. This also
differs structurally from the excluded Sjoding hidden-hypoxemia paper: Sjoding
is about a **static, race-stratified additive bias** in SpO2 vs SaO2 at a
point in time; this idea is about the **rate and direction of divergence
between two trend lines** over the resuscitation/ventilation course, in a
population with no race-conditioning angle at all. It also is not the
vasopressor-occult-dependence failure mode — there is no dose variable being
conditioned on; the entire signal is the cross-rater (proxy vs gold-standard)
disagreement trajectory.

**Novelty check (web search; no PubMed MCP available this session — flag
explicit).** Queries: `SpO2/FiO2 versus PaO2/FiO2 ratio trend discordance
ARDS proxy validity deterioration trajectory`; `oxygenation index trajectory
divergence SpO2/FiO2 PaO2/FiO2 widening gap silent deterioration before blood
gas drawn`. Found: extensive cross-sectional agreement/derivation literature
(Brown 2021 PMC9345592 review of "rationale and limitations"; 2026 ScienceDirect
review explicitly flagging "FiO2 variability and oximetry bias limit precision
around decision thresholds" as an open problem, not a solved one) and a
MIMIC-III PaO2-from-SpO2 **imputation** paper (different goal — filling in
missing PaO2, not detecting divergence as a predictive signal). No paper
found framing the S/F-P/F relationship as a **time-series decoupling-onset
detector**. This is consistent with the domain literature's own framing: the
2026 review explicitly says comprehensive trajectory-based clinical
interpretation is necessary but does not exist as a formal index — i.e., the
gap is acknowledged but unfilled. **Caveat: this is a web-search check, not a
PubMed-indexed systematic search; treat as provisional until confirmed with
PubMed/Embase before protocol lock.**

**Feasibility on MIMIC-IV.**
- SpO2: `chartevents` itemid 220277 (and legacy 646 in CareVue-era data);
  FiO2: 223835 (and 190/3420/3422 in CareVue); both charted frequently
  (often hourly or more) on any patient with supplemental O2/ventilation.
- PaO2/FiO2 (ABG): `labevents`/`chartevents` PaO2 (itemid 220224) paired with
  the FiO2 in effect at draw time (nearest preceding chartevent, standard
  mimic-code `bg` / oxygenation concept tables already do this join).
- Co-measurement frequency: ABGs are drawn far less often than pulse-ox
  readings (typically q4-12h in less acute patients, more often in unstable
  ones) — this is the natural "paired but asynchronous" structure the
  construct needs (S/F is the dense series, P/F the sparse ground-truth
  check), not a limitation to engineer around.
- Cohort: all MIMIC-IV ICU stays with ≥1 ABG and concurrent SpO2/FiO2
  charting — realistically tens of thousands of stays; restrict to
  ventilated or high-flow-O2 patients with ≥2 ABGs in the same admission to
  compute a divergence trajectory (likely high single-digit thousands to
  ~10-15k stays, comparable in size to prior MIMIC ARDS-phenotyping cohorts).
  eICU-CRD `lab` + `vitalPeriodic`/`respiratoryCharting` tables allow
  external replication, though eICU's coarser FiO2 capture is a known
  limitation flagged in the existing S/F-P/F correlation literature.
- Artifact risk: SpO2 nonlinearity above ~97% saturation (ceiling effect),
  motion/perfusion artifact, FiO2 charted as device setting rather than
  delivered fraction (especially nasal cannula/high-flow) — all standard,
  manageable confounds already discussed in the existing S/F literature, but
  must be handled (e.g., restrict primary analysis to SpO2 ≤97% per the
  Global ARDS definition's own SpO2/FiO2 eligibility rule) rather than
  ignored.

**Impact tier + biggest threat.** Tier: solid Critical Care Medicine /
Intensive Care Medicine — methodologically clean "monitoring blind spot"
story with direct clinical actionability (a real-time EHR alert: "your pulse
ox trend and your last two ABGs disagree in direction"). **Biggest threat:**
confounding by indication on *when* the ABG is drawn — clinicians draw ABGs
because they are already worried, so "P/F dropped while S/F looked stable"
may partly reflect that the ABG was drawn in response to a non-oximetry cue
(e.g., a ventilator alarm, exam finding) that the model never sees, inflating
the apparent decoupling signal. Mitigation: restrict to "routine" /
protocolized ABG draws (e.g., scheduled post-intubation or attending-rounds
panels) where feasible, or explicitly model and report the ABG-draw-trigger
selection process rather than treating ABG timing as exogenous. Second
threat: with only a web-search (not PubMed) check, there is real residual
risk a respiratory-specific journal already ran this — recommend a formal
PubMed/Embase confirmation pass (`SpO2/FiO2 PaO2/FiO2 trend divergence`,
`oxygenation index trajectory deterioration alarm`) before committing
analytic time.

---

## Idea 2: Cuff-vs-arterial-line blood pressure discordance restricted to the NORMOTENSIVE band, as a marker of vasomotor/autoregulatory strain — not a calibration-bias study

**Precise question.** Among ICU patients with simultaneous arterial-line and
cuff (NIBP) measurements, restricted to windows where **both** readings are
individually within a "normal"/non-alarming MAP band (e.g., 65-90 mmHg) —
i.e., neither signal alone would trigger concern — does a **widening
IBP-NIBP gap over time** (rather than a one-off discordant pair) predict
subsequent need for vasopressor initiation/escalation or unplanned
hemodynamic deterioration within the next 6-12h, independent of the absolute
MAP level of either signal?

**The novel construct and why it differs from the existing IBP/NIBP papers
(and from the excluded vasopressor-occult-dependence family).** The
2024-2025 MIMIC-IV IBP/NIBP papers found in this sweep (n=96,673 paired
measurements, n=6,060 patients; and the 27,022-pair hypotension-focused
study) characterize **static agreement/bias at a point in time**, mostly in
already-hypotensive or already-flagged ranges, and ask whether mortality risk
classification differs by method. This idea is deliberately restricted to
the band where **neither reading is abnormal** and asks about the **rate of
change of the gap itself** as a leading indicator — i.e., the two cuffs
"agreeing that things are fine" while progressively disagreeing with *each
other* is hypothesized to reflect early peripheral vasoconstriction/vascular
tone changes (which distort oscillometric cuff readings before MAP itself
falls) — a compensatory-mechanism-failing-quietly story, structurally
different from "two readings classify the same hypotensive event
differently." It is also explicitly NOT the vasopressor-occult-dependence
construct: there is no dose/VIS variable anywhere in the exposure or the
analysis — the entire exposure is built from two non-invasive/invasive
*pressure-measurement* signals, with vasopressor initiation as an *outcome*,
not a conditioning covariate, so the "dose→outcome in disguise" failure mode
the hard lesson warns about does not apply structurally (though it must still
be checked empirically — see threats below).

**Novelty check (web search).** Queries: `arterial line dampened waveform
versus cuff blood pressure unrecognized hypotension critically ill outcome`;
`arterial line insertion timing trigger hidden hypotension before invasive
monitoring placed MIMIC noninvasive cuff underestimate`; plus the general
IBP/NIBP queries above. Found: extensive **static bias/agreement** literature
(Bland-Altman style, including the 2025-2026 MDPI "practical approach for
dealing with widely discordant measurements" paper) and damping-artifact
literature, all focused on already-abnormal or single-timepoint comparisons.
No paper found restricting to the normotensive band and tracking **gap
trajectory** as a leading indicator of impending vasopressor need. **Verdict:
the IBP/NIBP discordance *construct itself* is well-published and partially
crowded — this idea survives only via the specific normotensive-band +
trajectory-velocity framing; if that framing is judged too close to existing
"both signals look fine but disagree" papers by a reviewer, this idea should
be considered MEDIUM-novelty, not high.** Recommend explicit reviewer-facing
language distinguishing "static discordant classification" (done) from "gap
acceleration as an early-warning trend" (not found).

**Feasibility on MIMIC-IV.**
- Arterial line MAP/SBP/DBP: `chartevents` itemids in the "Arterial Blood
  Pressure" family (220050/220051/220052 in MIMIC-IV; legacy 51/52/8368 etc.
  in CareVue). NIBP: 220179/220180/220181 (legacy 455/8441 etc.).
- Co-measurement: both are charted routinely (often q1h or more for arterial
  lines; NIBP cuffs typically cycle automatically or are checked
  intermittently as cross-check) in any patient with an arterial line —
  arterial lines are common in ICU (often 30-50% of stays), so realistic
  cohort size is in the high thousands to tens of thousands of stays with
  sufficient paired density to build a trajectory (need ≥3-4 paired readings
  per patient within the eligibility window to estimate a slope).
- Outcome: vasopressor initiation from `inputevents` (norepinephrine,
  vasopressin, phenylephrine, epinephrine, dopamine itemids) — clean,
  already-used-elsewhere-in-this-repo-family signal (cf. the VIS-based prior
  project), used here strictly as outcome, not exposure.
- Artifact risk: arterial-line damping/underdamping (technical, not
  physiologic, source of gap widening) is the single biggest confound and
  must be screened (e.g., via waveform quality flags if available in
  MIMIC-IV-WDB linkage, or via fast-flush-test proxies/heuristics if not);
  cuff size/limb edema is a second nuisance source. Both must be
  distinguished from the hypothesized vasomotor-tone mechanism, which is a
  real measurement-engineering burden, not a minor caveat.

**Impact tier + biggest threat.** Tier: Critical Care Medicine, plausible but
more incremental than Idea 1 given how crowded the underlying IBP/NIBP
literature already is — publishability hinges entirely on the trajectory
framing holding up, which is a narrower wedge than Idea 1's clean
proxy-vs-gold-standard temporal story. **Biggest threat:** (1) the normotensive-
band restriction may simply rediscover arterial-line damping/cuff-artifact
physics rather than a physiologic "compensation under strain" phenomenon —
this needs to be ruled out before claiming a phenotype; (2) reviewers
familiar with the 2025-2026 IBP/NIBP discordance wave may judge the
trajectory-vs-static distinction too thin to count as a new construct (this
is the single largest novelty risk in this document, flagged honestly rather
than downplayed).

---

## Idea 3 (exploratory / weaker — flagged, not discarded): Within-admission REVERSAL of which BP measurement method reads higher — a sign-flip rather than a magnitude-gap construct

**Precise question.** For patients with serial paired IBP/NIBP measurements,
does a **within-admission sign reversal** of the IBP-minus-NIBP difference
(e.g., NIBP > IBP for the first half of the stay, then IBP > NIBP for the
second half, or vice versa) — independent of the magnitude of either gap —
predict a clinically meaningful inflection point (new vasopressor, new organ
support, code event) better than monitoring either absolute gap or either
signal's absolute level?

**The novel construct and an honest self-critique.** Existing IBP/NIBP
papers report direction of bias as a population-level finding (e.g., "NIBP
systematically underestimates invasive MAP in septic patients") but do not,
as far as this search found, track **within-patient sign flips over time**
as an individual-level event-detection signal — the idea is structurally
closer to a change-point-detection problem than to a gradient/gap-magnitude
study. However, this is the weakest idea in the set: it is very plausibly
just a noisier, harder-to-interpret restatement of Idea 2 (any trajectory
that's "accelerating away from zero" will eventually look like it flipped
sign if it started slightly negative), and a skeptical reviewer could
reasonably argue it is the magnitude-gap story (already partially crowded)
wearing a thin disguise — i.e., it risks the same "dose-outcome-in-disguise"
critique pattern as the original vasopressor-occult-dependence project, just
substituting "BP gap magnitude" for "vasopressor dose." Included for
completeness and because the change-point framing is genuinely distinct
methodologically, but **not recommended as a lead idea** without first
establishing in pilot data that sign-reversal carries information beyond
slope/magnitude (e.g., via a likelihood-ratio test of a reversal-indicator
model against Idea 2's continuous-slope model).

**Novelty check (web search).** No dedicated query run beyond the IBP/NIBP
searches already performed for Idea 2 (same underlying literature applies);
this is a reframing of that literature rather than a new signal pair, so it
inherits Idea 2's novelty risk and adds the self-critique above. **Not
independently verified — treat as the least-vetted idea in this document.**

**Feasibility on MIMIC-IV.** Identical data sources to Idea 2 (same itemids,
same cohort). Feasible from a data-access standpoint; the open question is
purely whether the construct is real, not whether it can be measured.

**Impact tier + biggest threat.** Tier: speculative/exploratory at best —
should be treated as a secondary analysis nested inside Idea 2's protocol
(test whether a sign-reversal term adds information beyond the continuous
gap-slope term) rather than a standalone study. Biggest threat: high prior
probability that it collapses into Idea 2 once formally tested, with no
independent contribution — i.e., it may not be a distinct idea at all.

---

## Ranking and recommendation

1. **Idea 1 (S/F vs P/F temporal decoupling-onset)** — strongest novelty
   margin found in this sweep (cross-sectional S/F-P/F agreement is heavily
   published; the trajectory/decoupling-onset framing was not found
   anywhere), clean mechanism (proxy-validity collapse, not a renamed dose
   variable), clear clinical actionability (real-time EHR divergence alert),
   and a tractable MIMIC-IV cohort via standard ABG+pulse-ox+FiO2 itemids.
   Main open risk is the ABG-draw-timing confounder (clinicians order ABGs
   when worried), which is a design problem to solve, not a fatal novelty
   flaw — and a formal PubMed/Embase pass (not available this session) is
   recommended before protocol lock, since only web search was used.

2. **Idea 2 (normotensive-band IBP-NIBP gap trajectory)** — clinically
   intuitive and feasible, but sits inside a now-crowded IBP/NIBP discordance
   literature (multiple 2024-2026 MIMIC-IV papers on exactly this signal
   pair). Survives only via the normotensive-band + gap-*trajectory* (not
   static-gap) framing, and that framing must be defended explicitly against
   reviewers who will know the 2024-2025 MIMIC-IV IBP/NIBP papers. Ranked
   second because the novelty margin is real but thinner than Idea 1's, and
   because arterial-line damping artifact is a serious, labor-intensive
   confound to rule out.

3. **Idea 3 (BP-gap sign-reversal)** — included for completeness but not
   recommended as a standalone lead; most likely to be absorbed into Idea 2
   as a secondary/sensitivity analysis once tested, and has the weakest,
   least-independently-verified novelty check of the three.

**General caution for whoever picks this up:** this novelty sweep used web
search only (no PubMed/Embase MCP tool was available in this session). The
"obvious" signal-disagreement pairs in ICU monitoring — BP method pairs, CO2
gradients, temperature gradients, oxygenation-index pairs, perfusion/lactate
pairs, neuro-exam pairs, ventilator synchrony — are overwhelmingly already
named and published, several as recently as 2025-2026, which means this
sub-field is moving fast and a formal database search immediately before
protocol lock is not optional due-diligence here, it is load-bearing.
