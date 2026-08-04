# Pivot ideas: physiological dynamics/coupling on MIMIC-IV / eICU-CRD

Status: candidate generation for a CCM/ICM/Anesthesiology-tier paper. Not yet
scoped against this repo's pipeline — this is a research-direction memo, not
an implementation plan. Do not commit without review.

Search tool used: PubMed (`mcp__...__search_articles`), literal AND-expanded
term matching, no fuzzy/semantic fallback. A "0 hits" result means PubMed's
indexed title/abstract/MeSH text contains no article matching the literal
conjunction of terms — it is suggestive of a gap, not proof of one (a paper
using different vocabulary, e.g. "autonomic-cardiovascular synchronization,"
could still exist and be missed). Treat all novelty verdicts below as
"no obvious prior art found by term search," not "confirmed first-in-field."
Each idea should get a second, vocabulary-varied search pass (and a
forward-citation check on the closest related papers) before committing real
analysis time.

---

## Idea 1 — Cross-system recovery-shape divergence after a shared perturbation
("perturbation-response asymmetry")

**Precise question.** After a discrete hemodynamic perturbation common to
many ICU stays (fluid bolus, vasopressor rate step-down, the post-extubation
window), do HR and MAP/SBP return to baseline along systematically different
*shapes* (time-to-50%-recovery, overshoot, monotonicity) from each other, and
does the degree of **shape mismatch between the two recovering signals**
(not their absolute recovery times) predict short-term deterioration
(re-intubation, pressor restart, rapid response, 24h mortality)?

**The novel construct.** Most "recovery dynamics" work (fluid responsiveness,
post-bolus MAP slope) treats one signal in isolation. The proposed construct
is the *within-patient, within-episode discordance between two systems'
return-to-baseline trajectories* — e.g., HR recovers exponentially while MAP
recovers with a damped-oscillatory overshoot, or vice versa — quantified as a
shape-distance (DTW or functional-PCA distance between normalized recovery
curves) rather than a magnitude or a single slope. This has no established
name; "fluid responsiveness," "hemodynamic recovery time," and "rebound
hypotension" are all single-signal magnitude/time constructs, not a
cross-signal shape-mismatch construct.

**PubMed novelty check.**
- "post-resuscitation overshoot blood pressure recovery shape septic shock
  outcome" → 0 hits.
- "recovery slope after hypotensive episode ICU electronic health record" →
  0 hits.
- "vasopressor discontinuation rebound hypotension time to recurrence ICU" →
  0 hits.
- "fluid bolus blood pressure response trajectory shape fluid responsiveness
  MIMIC" → 0 hits.
- What *does* exist (broader searches): conventional fluid-responsiveness
  literature (single-signal, magnitude-based: does MAP/CO rise ≥10-15% after
  a bolus) and "weaning failure" prediction from pre-extubation static
  features — both well-trodden but neither examines cross-signal shape
  discordance during the recovery window. Gap appears real under this search
  strategy.

**Feasibility on MIMIC-IV.** `chartevents` itemids for HR, NBP/ABP (systolic,
diastolic, mean), tied to `inputevents` (crystalloid boluses, identified by
rate/volume/duration heuristics already common in fluid-responsiveness MIMIC
papers) and `inputevents`/`pharmacy` for vasopressor rate changes. Episode
detection (bolus start, pressor taper start) is the main engineering task —
your repo already has a proven disk-safe streaming filter for the 30GB
chartevents table, which is the right tool for extracting ±60-90 min windows
around tens of thousands of candidate episodes. Cohort: likely 5,000-15,000
qualifying bolus/taper episodes across MIMIC-IV after applying minimum
sampling-density and artifact filters. eICU-CRD (`vitalPeriodic`, regularly
sampled) is a strong external-replication target since the shape-matching
analysis wants evenly-sampled series. **Key analytic risk:** nursing
charting cadence in MIMIC-IV is irregular (manual vitals q1-4h outside
arterial-line patients), so "shape" estimation is only trustworthy in the
arterial-line subset (continuous ABP) — this shrinks the usable cohort
substantially and biases toward sicker patients (those with a-lines), which
must be addressed explicitly (it's a selection effect, not necessarily a
confound on the outcome relationship, but reviewers will ask).

**Impact tier + biggest threat.** Tier: strong CCM/ICM if effect holds and
replicates in eICU — "two systems recovering in discordant shapes" is a
clean, intuitive, clinically actionable signal (could feed an early-warning
score) and a fundamentally relational/dynamic construct, fitting the brief.
Biggest threat: **confounding by perturbation magnitude and case-mix
severity** — sicker patients get bigger boluses/longer pressor courses and
also have worse baseline autonomic regulation, so shape-mismatch could just
be a re-encoding of illness severity (i.e., a more complex SOFA-correlate).
Must show the dynamics signal is incremental over admission severity score
and over each signal's own magnitude-based recovery metric, or it's DOA as
"another way to detect sick patients."

---

## Idea 2 — Lag-structure inversion between HR and MAP ("temporal lead-lag flip")

**Precise question.** Under normal autonomic regulation, transient MAP
perturbations lead HR responses (baroreflex) with a consistent short lag
(~1-3 beats/sec scale, here approximated at minute-resolution as MAP
changes preceding compensatory HR changes within a short window). Does the
**sign or magnitude of the cross-correlation lag between MAP and HR invert
or flatten** in the hours preceding septic shock onset, AKI, or death —
independent of either signal's mean, variance, or trend — and is this
"lead-lag flip" detectable at MIMIC-IV's native charting resolution (not
just at beat-to-beat physiologic-waveform resolution, which requires
MIMIC-IV Waveform Database / MIMIC-III matched waveforms)?

**The novel construct.** Not "loss of HRV" (named, established) and not
"baroreflex sensitivity" (named, established physiology metric with its own
literature in anesthesia/neurology). The construct here is *directional
asymmetry of the lead-lag relationship over a rolling window*, i.e., whether
MAP-leads-HR cross-correlation peaks at a positive vs. near-zero vs.
negative lag, tracked as a trajectory and tested for **inversion events**
preceding decompensation, distinct from baroreflex sensitivity (a gain/slope
metric, not a lag-sign metric) and distinct from simple coupling-strength
loss (Idea 3 below).

**PubMed novelty check.**
- "lead lag relationship blood pressure heart rate Granger causality ICU" →
  0 hits.
- "cross correlation lag heart rate mean arterial pressure baroreflex sepsis
  outcome" → 0 hits.
- Broader context (not searched fresh here but known from the field):
  baroreflex sensitivity (BRS) via sequence method or spectral transfer
  function is a *large*, decades-old, named literature (autonomic/cardiology,
  mostly in stable outpatients or post-MI cohorts) — reviewers will demand a
  sharp distinction from BRS. The proposed construct's novelty rests entirely
  on (a) being a sign/topology feature rather than a gain feature, and (b)
  being studied prospectively for inversion *events* in unselected ICU
  admissions at EHR-resolution, which BRS literature essentially never does
  (BRS needs beat-to-beat waveform data, a different and much smaller MIMIC
  subset).

**Feasibility on MIMIC-IV.** At minute/hourly chartevents resolution, true
baroreflex-timescale lag (seconds) is unobservable — this idea is only
honest if reframed at the timescale MIMIC-IV actually supports (rolling
20-60 min windows, lag tested in 1-5 minute steps) which is a *different*,
slower physiological phenomenon than classical BRS and should be named and
defended as such (e.g., "slow hemodynamic coupling," not baroreflex). For
beat-to-beat fidelity, MIMIC-IV Waveform Database (a separate, much smaller,
ICU-specific high-resolution physiologic waveform release) would be needed —
feasible but a materially heavier data-engineering lift than chartevents
streaming. Cohort at chartevents resolution: similar to Idea 1, gated by
arterial-line continuous ABP availability for usable lag estimation; coarser
NBP-only patients would need a sensitivity-only role. **Key analytic risk:**
at coarse sampling, lag estimates are extremely noisy per-window; this needs
either the waveform database (cost: scope/engineering) or heavy smoothing
that risks washing out the very signal being claimed (artifact risk is the
dominant concern, more so than confounding).

**Impact tier + biggest threat.** Tier: could be very high (mechanistically
interesting, autonomic-failure framing resonates with sepsis pathophysiology
reviewers) *if* done on waveform-resolution data; markedly lower and more
vulnerable to "this is just noisy BRS" criticism if confined to chartevents
resolution. Biggest threat: **construct conflation with baroreflex
sensitivity** — without crisp methodological separation (sign/topology vs.
gain; minute-scale vs. beat-scale) a reviewer will say "you reinvented BRS
under a new name," which is exactly the named-index trap this brief warns
against. This idea is rank-2 specifically because avoiding that trap requires
either the harder waveform dataset or careful, defensible reframing.

---

## Idea 3 — Multi-signal coupling collapse as a leading (not concurrent) indicator
("coupling-collapse lead time")

**Precise question.** Define a rolling, multi-pair coupling-strength
trajectory (e.g., pairwise dynamic time warping similarity or windowed
cross-correlation magnitude, computed simultaneously for HR-MAP, HR-RR,
MAP-RR, and HR-SpO2) per patient over the ICU stay. Does the **trajectory**
of aggregate coupling strength — specifically a sustained downward trend
over hours, not a single low value — have a measurable **lead time** before
clinically-recognized deterioration (vasopressor initiation, intubation,
RRT activation, death), and is that lead time long enough (e.g., >4-6h) to
be actionable, compared with existing single-signal early-warning approaches?

**The novel construct.** This is explicitly *not* "physiological variability
collapse" in any one signal (HRV collapse is named/established) and not a
composite severity score (SOFA/NEWS are point-in-time, not trajectory/lead-
time constructs over inter-signal coupling). The construct is the **temporal
lead/lag between a multi-pair coupling-decline trend and clinical
recognition**, treating "how much earlier does the relational signal fire
than the clinical team" as the primary outcome variable, rather than just
classification AUC. Framing the outcome as *lead time of a relational
signal* (not "can we predict deterioration," which is heavily studied) is
the novelty hook.

**PubMed novelty check.**
- "decoupling physiological signals critical illness deterioration
  prediction" → 0 hits.
- "autonomic decoupling multiorgan ICU vital signs network" → 0 hits.
- "cardiorespiratory coupling critically ill outcome" → 4 hits, all
  irrelevant on inspection (a shock-management perspective piece by Pinsky,
  Crit Care Med 2026, [DOI](https://doi.org/10.1097/CCM.0000000000007115);
  a neonatal lung-ultrasound/echo follow-up commentary,
  [DOI](https://doi.org/10.1007/s00431-026-06753-5); a caregiver PTSD-
  trajectory study, [DOI](https://doi.org/10.1001/jamanetworkopen.2023.7448);
  and a pediatric ECLS-after-transplant consensus paper — none examine
  inter-signal coupling). According to PubMed, none of the literal-term
  hits constitute prior art for this construct.
- This is the most "deterioration prediction"-adjacent of the three ideas,
  which is both its strength (clear clinical hook: early warning) and its
  risk (closest to a saturated literature of MIMIC-based early-warning
  models — the *lead-time-of-a-relational-signal* framing is what keeps it
  distinct, and that framing must be foregrounded, not buried, in any paper).

**Feasibility on MIMIC-IV.** Heaviest engineering lift of the three: needs
simultaneous, reasonably dense sampling of 4 signal types per patient over
multi-hour rolling windows, computed pairwise, then a trend-detection layer
(e.g., CUSUM or Mann-Kendall on the rolling coupling-strength series) plus
a survival-style lead-time analysis against time-stamped clinical events
(`inputevents` for first pressor, `procedureevents` for intubation/RRT).
This is exactly the multi-table, long-running streaming-filter problem your
existing chartevents pipeline is built for. Cohort: full general MIMIC-IV
ICU population is usable (unlike Ideas 1-2, doesn't strictly require
arterial lines if windows are long enough to tolerate NBP sparsity, though
a-line patients will have cleaner estimates) — likely tens of thousands of
stays, with an a-line-restricted high-fidelity subgroup as primary analysis
and full cohort as sensitivity/generalizability check. eICU-CRD is a solid
replication cohort (`vitalPeriodic` table is well-suited). **Key analytic
risk:** multiple-pairwise-coupling trend detection has many researcher
degrees of freedom (window length, pair selection, trend statistic,
event-time definition) — pre-registration of the exact pipeline (consistent
with this repo's general philosophy of config-driven, pre-specified
analysis) is essential to avoid this becoming an overfit, multiplicity-
laundered result.

**Impact tier + biggest threat.** Tier: highest ceiling of the three —
"early warning system with a defensible, mechanistically-motivated lead
time, validated on two databases" is squarely CCM/ICM-cover-worthy if it
holds up, and the *lead-time* framing (vs. plain AUC) is a genuinely
different scientific question from the saturated MIMIC early-warning-score
literature. Biggest threat: **multiplicity/overfitting and the "known
result in disguise" risk** — because severity scores and HRV-collapse
literature already predict deterioration, a coupling-collapse signal that
merely correlates with (rather than adds incremental, earlier-firing value
over) those known predictors will be read as a reskin of existing
early-warning work. The paper lives or dies on (a) strict temporal
lead-time framing and (b) incremental value over SOFA/NEWS2 trend and
single-signal HRV trend in the same cohort.

---

## Ranking

1. **Idea 3 (coupling-collapse lead time)** — highest impact ceiling, full
   chartevents cohort feasible with the existing streaming pipeline, and the
   PubMed search came back cleanest (the 4 "cardiorespiratory coupling"
   hits were all clearly off-topic on inspection, [DOI](https://doi.org/10.1097/CCM.0000000000007115),
   [DOI](https://doi.org/10.1007/s00431-026-06753-5),
   [DOI](https://doi.org/10.1001/jamanetworkopen.2023.7448)).
   Its central risk (overfitting/multiplicity, looking like a reskinned
   early-warning score) is manageable with pre-registration discipline this
   project already practices elsewhere (config-driven, hash-frozen
   pipelines). Recommend as the lead candidate.

2. **Idea 1 (perturbation-response shape divergence)** — cleanest, most
   self-contained novelty story (genuinely no prior art found across four
   targeted searches), clearest mechanistic narrative, and a smaller,
   well-defined cohort (arterial-line bolus/taper episodes) that's easier to
   execute well than Idea 3's full multi-pair trend pipeline. Main weakness
   is the a-line selection effect shrinking and skewing the cohort. Strong
   second choice — could even be a faster first paper while Idea 3 is built
   out, since they share infrastructure (episode extraction from
   chartevents + inputevents).

3. **Idea 2 (lead-lag inversion / "slow coupling")** ranks third: real
   novelty at chartevents resolution, but only because it's a watered-down,
   slower-timescale cousin of the well-established baroreflex-sensitivity
   literature — a reviewer is likely to demand either MIMIC-IV Waveform
   Database-resolution data (heavier lift) or very careful reframing to
   avoid the "renamed BRS" critique this brief explicitly warns against.

Per-tool legal notice (PubMed MCP server, applies to citations above):
results are attributed "According to PubMed," with DOIs linked, as required.
