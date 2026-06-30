# Intraoperative waveform-derived constructs on VitalDB (+ MOVER)

Status: idea-generation only, NOT committed, NOT part of the HEEDB EEG-phenotype
study (different dataset, different domain — perioperative physiology, not
EEG phenotyping). This memo is scoped exactly as requested: novel
waveform-derived constructs from VitalDB's high-resolution intraoperative
signals (ABP, ECG, PPG, capnography, BIS/EEG, rSO2 where present) that
predict postoperative outcomes and are invisible to crude summary statistics
(TWA-MAP, AUC-MAP<65, VIS, total vasopressor dose).

**Constraint enforced throughout** (per the brief's hard lesson): disqualify
any candidate that (a) reduces to dose/load → outcome (the well-trodden
TWA-MAP / AUC-MAP<65 / VIS-style literature), or (b) is a restated **named**
index — augmentation index, PVI (pleth variability index), SVV, HPI
(Hypotension Prediction Index), PPV, Eadyn, COx (cerebral oximetry index) are
all named and already studied; a candidate built on one of these is only
novel if the **temporal trajectory or cross-signal coupling framing** is
itself new, and that distinction is argued explicitly per idea, not asserted.

Novelty was checked by web search (general web search, not a dedicated
biomedical-literature MCP tool in this session) against PubMed-indexed,
medRxiv, and grey-literature sources. A "no hit" result is suggestive of a
gap, not proof of one — vocabulary variation could hide existing work. Each
verdict below states what *was* found and how the proposed construct differs
from it, rather than claiming a clean field.

---

## VitalDB signal-availability facts that gate feasibility (checked, not assumed)

- **ABP waveform**: ~100–500 Hz invasive arterial line, present in the large
  majority of cases with an a-line (most major/intermediate surgery cases).
  This is the highest-yield, most universally available high-res signal.
- **PPG (pleth)**: near-universal (pulse oximeter on essentially every case),
  ~100 Hz.
- **ECG**: near-universal, lead II typically, ~500 Hz.
- **Capnography (EtCO2 waveform)**: present for all general-anesthesia/
  intubated or supraglottic-airway cases; absent for regional/MAC cases.
- **BIS/EEG**: BIS *index* (numeric trend, 1 Hz-ish) is present whenever a
  BIS monitor was used (a meaningful but not universal subset of cases —
  selection by case type/era/institution). The **raw BIS EEG waveform**
  (tracks `BIS/EEG1_WAV`, `BIS/EEG2_WAV`, ~128–180 Hz) is present for a
  *smaller* subset still (monitor-model- and era-dependent; some Covidien/
  Philips BIS units do not export the raw waveform into the `.vital` file —
  this is a documented VitalDB user-board issue, not a rare edge case).
  **Any construct requiring the raw BIS waveform (not just the BIS index)
  must be scoped as a planned subgroup analysis, with the BIS-index-only
  fallback stated up front.**
- **Cerebral oximetry (rSO2/NIRS)**: present in only a minority of VitalDB
  cases (institution/era-dependent). COx-style autoregulation indices that
  depend on rSO2 are therefore the *least* feasible class on VitalDB — this
  is exactly why constructs below prefer BIS+ABP coupling (broadly available)
  over rSO2+ABP coupling (the established but narrow COx approach).
- **MOVER** (Multicenter periOperative Outcomes group + VitalDB-like
  resource) is named in the brief as a secondary/replication asset; it is
  EHR-summary-heavy and does not provide the same waveform density as
  VitalDB, so it is treated here as an **external-validation target for
  outcome labels and coarse trends**, not a primary waveform source.

---

## Idea 1 (TOP RANK): Wave-reflection recovery half-life after a discrete hemodynamic perturbation ("reflection recovery time")

**Precise definition.** For each arterial-pressure beat, decompose the
waveform into forward and backward (reflected) components (wave-separation
analysis using the standard triangular/exponential flow approximation, or
simpler: track the augmentation index AIx and the systolic-shoulder-to-peak
timing per beat — these are named, static, single-beat quantities). The
**novel object** is not AIx itself but its **recovery time-course after a
discrete perturbation** common in VitalDB cases: induction-of-anesthesia MAP
drop, a pneumoperitoneum insufflation step (laparoscopic cases — a sudden,
well-timed afterload/preload perturbation recorded as an event in many
VitalDB case logs), aortic cross-clamp/declamp (vascular cases), or a
vasopressor bolus. Fit the AIx (or backward-wave amplitude) trajectory across
the ~60–180 s following the perturbation to a recovery model (exponential or
biexponential) and extract a **half-life of wave-reflection recovery**, distinct
from (a) the static AIx value, (b) the MAP recovery half-life (a different,
already-studied magnitude/time construct), and (c) the binary "reflected
wave present/absent" finding reported in the one liver-transplant anhepatic-
phase study found below. The construct is the **shape and time constant of
reflection-magnitude recovery**, not reflection magnitude itself, and not MAP
recovery — it isolates how fast peripheral vascular tone re-establishes a
normal forward/backward wave balance after a shock to the system, which a
TWA-MAP or AUC-MAP<65 summary cannot see at all (both discard within-event
waveform shape entirely).

**Why it needs the waveform.** AIx/wave-separation requires the full
high-frequency pressure contour per beat (systolic shoulder, dicrotic notch,
diastolic decay shape); a summary statistic over a window destroys exactly
the morphological information needed. The *recovery trajectory* additionally
requires beat-by-beat resolution across the perturbation window, not a
pre/post mean.

**Postop outcome.** Hypothesized to predict postoperative AKI and
myocardial injury (MINS) — slow reflection-recovery implies sluggish
vascular re-equilibration, a plausible mechanistic link to end-organ
hypoperfusion episodes that a single MAP threshold misses (the perturbation
may never cross AUC-MAP<65 yet still reflect impaired vasoregulatory
reserve). Also plausible for postoperative delirium via the same
vasoregulatory-reserve mechanism.

**Novelty check.** Searches: "augmentation index trajectory wave reflection
time-varying surgery anesthesia outcome novel," "dicrotic notch dynamics
intraoperative arterial waveform postoperative outcome prediction." Found:
(1) augmentation index is a long-established, *static*, named cardiovascular-
risk marker (large hypertension/CV-risk literature, not surgery-specific);
(2) one very recent, narrow study (liver-transplant anhepatic phase,
ClinicalTrials.gov NCT03694301) noting that the *reflected wave disappears*
during the anhepatic phase and proposing reflected-wave presence/absence at
reperfusion as a graft-function marker for 30-day mortality/AKI/ICU stay —
this is the closest prior art and is a **binary presence/absence at one
fixed surgical moment**, not a general recovery-kinetics construct applicable
across perturbation types and surgeries. No study found treating
wave-reflection recovery *kinetics* (half-life/time-constant) as a
generalizable, perturbation-triggered, repeated-measures construct across a
broad surgical cohort. Verdict: **plausibly novel** — the liver-transplant
finding is suggestive precedent that motivates the mechanism, not a
collision with the proposed construct.

**Biggest feasibility/artifact threat.** Wave-separation analysis classically
needs a measured or assumed flow waveform (true forward/backward separation
requires simultaneous flow, e.g., from Doppler or a validated flow
approximation) — VitalDB gives pressure-only at the radial/femoral line, so
this must use a pressure-only proxy (AIx from the inflection point, or a
single-port wave-separation approximation), which is a weaker, more
artifact-prone substitute and must be validated against waveform quality
(damping, catheter whip, motion artifact during position changes is
especially likely right at insufflation/clamp events — exactly the windows
of interest). Radial-vs-femoral catheter site also changes AIx morphology
systematically and must be a stratification variable, not an afterthought.

---

## Idea 2: BIS-burst-onset MAP threshold as a cuff-free, waveform-paired cerebral-autoregulation surrogate ("EEG-pressure passivity point")

**Precise definition.** For cases with continuous BIS index (or, in the
smaller subgroup, raw BIS/EEG waveform) co-recorded with continuous ABP,
define a per-patient, per-case **MAP value at which the EEG first transitions
into burst-suppression or a marked discontinuity** during a slow intraoperative
MAP decline (induction, or a spontaneous/iatrogenic hypotensive drift) — i.e.,
the blood pressure at which cortical electrical activity stops being
sustained, used as a direct, individual-patient lower-limit-of-autoregulation
surrogate. This is explicitly **not** the established COx (correlation of
rSO2 and MAP, requiring NIRS, present in only a VitalDB minority) and not
"burst-suppression ratio/duration → delirium" (a *dose* construct, the
already-saturated literature this brief asks to avoid). The novel framing is
the **MAP value at the moment of EEG state transition**, extracted per case
from the ABP-BIS *temporal coupling* at a specific event (suppression onset),
analogous in spirit to MAPopt/BISopt curve-fitting but computed from a
broadly-available signal pair (BIS+ABP) rather than the narrow rSO2+ABP pair,
and framed as an event-threshold rather than a continuously-fit correlation
coefficient (COx) — a genuinely different estimator with different data
requirements and different failure modes.

**Why it needs the waveform.** Requires beat-resolution MAP aligned in time
with the BIS suppression-onset timestamp (or raw EEG amplitude collapse);
a session-mean BIS or session-mean MAP cannot localize the transition point.

**Postop outcome.** Lower (more negative) personalized suppression-onset MAP
plausibly indicates preserved autoregulatory reserve and predicts lower risk
of postoperative delirium/cognitive dysfunction; a high (close-to-baseline)
suppression-onset MAP flags a patient whose brain is unusually pressure-
passive, predicting delirium/POCD at MAP levels conventional thresholds
(MAP<65) would call "safe."

**Novelty check.** Searches: "cerebral autoregulation BIS EEG suppression
mean arterial pressure intraoperative optimal MAP cerebral oximetry,"
"pressure passive EEG / EEG suppression threshold mean arterial pressure
individualized autoregulation surrogate." Found: COx/MAPopt/BISopt (NIRS-rSO2-
correlation-based optimal-MAP literature) is well established but
**structurally different** — it is a continuously-fit Pearson-correlation
curve over rSO2 vs. MAP requiring NIRS, not an EEG-state-transition event
threshold from BIS+ABP. Burst-suppression-as-delirium-predictor literature is
large but entirely dose/duration-based (BSR%, suppression minutes), never
framed as "the MAP value at the transition." No study found using BIS+ABP
(without NIRS) to derive a per-patient suppression-onset MAP. Verdict:
**novel framing of an adjacent, established idea (autoregulation-optimal-MAP)
using a different, more available signal pair and a different estimator
(threshold-detection vs. correlation-curve-fit)** — must be argued carefully
in any writeup to avoid looking like a BISopt re-skin; the discriminating
claim is "event-threshold from ubiquitous BIS+ABP" vs. "correlation-curve
from scarce NIRS+ABP."

**Biggest feasibility/artifact threat.** Burst suppression has many
non-hemodynamic causes (anesthetic depth/dose itself, hypothermia, age,
hypocapnia) that are strong confounders of "MAP at suppression onset" —
a deep anesthetic alone can trigger suppression at a normal MAP, which would
masquerade as "pressure-passive" when it is actually drug-driven. Must
condition on simultaneously-recorded end-tidal anesthetic concentration/MAC
and exclude/stratify suppression events that co-occur with anesthetic-depth
increases rather than MAP decline, or the construct collapses into "deeply
anesthetized patients have worse outcomes" (a known, dose-shaped confound —
precisely the trap the brief warns against). Raw-waveform subgroup (vs.
BIS-index-only) availability further limits sample size, as noted above.

---

## Idea 3: Cross-signal recovery-shape mismatch after a vasopressor bolus — ABP vs. PPG amplitude divergence ("pressor-response shape discordance")

**Precise definition.** After a discrete vasopressor bolus (phenylephrine or
ephedrine push, identifiable from VitalDB drug-event annotations), extract
the post-bolus recovery trajectories of two *different* signals over the
following ~60–120 s: (a) the arterial pressure waveform's pulse-pressure
trajectory, and (b) the PPG pulse amplitude trajectory (a peripheral-
perfusion proxy). Both individually recover toward a new steady state, but
the novel construct is the **shape mismatch between the two recovery curves**
— e.g., central pressure normalizes quickly while peripheral PPG amplitude
remains suppressed for much longer (suggesting persistent peripheral
vasoconstriction despite restored central pressure), or the reverse —
quantified as a functional-distance (DTW or normalized curve-shape distance)
between the two recovery trajectories, not the magnitude or timing of either
alone. This deliberately follows the same "cross-signal recovery-shape
discordance" logic already used successfully in this repo's ICU-domain
pivot memo (`docs/PIVOT_IDEAS_DYNAMICS.md`, Idea 1), here transplanted to the
intraoperative, waveform-resolution, vasopressor-bolus setting, which is a
different signal pair, different timescale, and different triggering event,
so it is not a duplicate — it is the same *meta-construct* (discordant
recovery shape, not magnitude) applied to a new domain, which should be
disclosed explicitly as such rather than presented as independently
invented.

**Why it needs the waveform.** Both pulse-pressure-recovery and PPG-
amplitude-recovery are inherently beat-to-beat, sub-minute phenomena;
collapsing to a pre/post bolus mean MAP (the standard "did the pressor
work" outcome in existing pressor-response literature) discards exactly the
shape information this construct is built on.

**Postop outcome.** Central-fast/peripheral-slow recovery discordance
(persistent peripheral vasoconstriction after central normalization)
plausibly predicts impaired tissue perfusion despite "normal" pressure
readings — a candidate predictor of postoperative AKI or delayed surgical-
site healing/wound complications, outcomes that are specifically about
peripheral/microvascular perfusion rather than central hemodynamics.

**Novelty check.** Searches: "vasopressor bolus blood pressure recovery
dynamics shape vascular reactivity phenotype intraoperative," "PPG ABP pulse
wave amplitude ratio coupling drift vasopressor phenylephrine norepinephrine
tracking intraoperative." Found: PPG-amplitude/pulse-pressure ratio as a
*static* relative-compliance marker (used in a liver-graft-reperfusion
beat-to-beat study and a norepinephrine-titration case series); dynamic
arterial elastance (Eadyn) as a named, established afterload-coupling index
computed from pulse-pressure variation, not from a post-bolus recovery
trajectory. No study found explicitly quantifying the **shape mismatch
between two independently-recovering signals** (central ABP vs. peripheral
PPG) after a vasopressor bolus as the primary exposure (as opposed to a
ratio or ad hoc trend description). Verdict: **novel as a shape-discordance
metric**, modest risk that it collides conceptually with PPG/PP-ratio
literature if not carefully distinguished — the distinguishing claim is
"divergence of two recovery *curves* over time" vs. "ratio of two
*instantaneous* amplitudes," which must be foregrounded.

**Biggest feasibility/artifact threat.** PPG amplitude is exquisitely
sensitive to non-hemodynamic artifact (probe repositioning, ambient light,
patient/limb movement, temperature-driven vasomotion, pulse-oximeter
recalibration) — far noisier than the ABP channel. A spurious PPG-amplitude
dip coincident with a bolus (e.g., a position change for the same surgical
step that prompted the pressor) could fully masquerade as "peripheral
vasoconstriction," so events must be filtered for concurrent motion/position-
change/electrocautery artifact flags, and bolus events must be drawn from
clean, unambiguous drug-administration timestamps (VitalDB's medication
event logging completeness and timestamp precision is itself variable across
cases/institutions and needs auditing before this becomes a primary
analysis).

---

## Idea 4: Capnogram-ABP phase coupling during mechanical ventilation — pulsus paradoxus magnitude *trajectory* as an occult hypovolemia/right-heart-strain proxy ("ventilation-perfusion phase drift")

**Precise definition.** During positive-pressure ventilation, every arterial
pressure waveform carries a respiratory-induced oscillation (the basis of
PPV/SVV, both named, established fluid-responsiveness indices). The novel
construct here is not PPV/SVV's *magnitude* but the **phase relationship
between the capnogram's respiratory cycle and the ABP's respiratory-induced
oscillation**, tracked continuously, and specifically its **drift over the
course of surgery** (not a single measured value at one fluid-challenge
moment, which is exactly what PPV/SVV already are). A consistent phase lag
between end-inspiration (capnogram) and the ABP trough/peak that drifts
(lengthens or shortens) over hours — rather than a single static PPV
number — is hypothesized to track evolving right-heart/pulmonary-vascular
load distinct from a momentary volume-responsiveness reading.

**Why it needs the waveform.** Phase-lag estimation between two periodic
signals requires the full waveform of both the capnogram and the ABP at
native sampling rate across many respiratory cycles; PPV/SVV themselves
already require waveform-level beat detection, but the **trajectory of the
phase relationship over the case**, as opposed to a windowed average PPV, is
the new element and cannot be recovered from any published summary
statistic.

**Postop outcome.** Hypothesized link to postoperative pulmonary
complications and unplanned post-op escalation of respiratory/cardiac
support, via a right-heart-strain/ventilation-perfusion-mismatch mechanism
that evolves with surgical duration, fluid administration, and
pneumoperitoneum/positioning — not captured by a single intraoperative PPV
spot-check.

**Novelty check.** Searches: "capnogram arterial pressure coupling
ventilation-perfusion intraoperative waveform novel postoperative
pulmonary." Found PPV/SVV (named, huge fluid-responsiveness literature,
explicitly excluded by the brief), capnogram-only waveform-morphology work
(CPR/ROSC contexts, not surgical), and EIT-based V/Q calibration using ABP
(a 2025 paper, but using ABP for a *different* purpose — calibrating
impedance tomography, not deriving a capnogram-ABP phase-coupling
trajectory). No collision found for the specific phase-coupling-drift
construct. Verdict: **tentatively novel**, but this is the **weakest** of
the four ideas — it sits closest to the named PPV/SVV space and the
mechanistic story (phase drift → right-heart strain → pulmonary
complications) is the least worked-out of the set; flagged as such rather
than omitted, per this repo's stated practice of disclosing weak links
honestly.

**Biggest feasibility/artifact threat.** Restricted to intubated/
mechanically-ventilated cases with a regular respiratory rate (irregular
ventilator modes, spontaneous-breathing trials, or surgeon-requested
apnea/breath-holds for imaging would break phase estimation entirely);
electrocautery and capnogram-line water condensation are common,
underappreciated VitalDB artifact sources that would corrupt phase
estimates without an obvious failure signature (i.e., the analysis could
silently produce plausible-looking but wrong phase trajectories) — robust
artifact/quality flags on both channels are a prerequisite, not an add-on.

---

## Ranking

1. **Idea 1 (wave-reflection recovery half-life)** — strongest novelty
   margin (closest prior art is a single narrow liver-transplant
   presence/absence finding, not a recovery-kinetics construct), uses the
   single most universally available VitalDB high-res signal (ABP alone, no
   dependence on the scarcer BIS-waveform or rSO2 subsets), and has a clean
   mechanistic story (vasoregulatory reserve) connecting directly to AKI/MINS
   outcomes that VitalDB is well powered for. Main risk is pressure-only
   wave-separation being a weaker proxy than true flow-based separation —
   manageable with care, not disqualifying.

2. **Idea 3 (pressor-response shape discordance, ABP vs. PPG)** — second
   because the meta-construct (cross-signal recovery-shape mismatch, not
   magnitude) is borrowed deliberately from this repo's own prior ICU-domain
   work and re-applied to a new signal pair/timescale/trigger, which is
   honest, defensible novelty but not first-principles novel the way Idea 1
   is. Outcome story (peripheral perfusion vs. central pressure) is
   clinically intuitive and PPG/ABP are both near-universally available,
   maximizing cohort size — but PPG's artifact sensitivity is the dominant
   practical threat and will demand serious quality-control engineering
   before the construct is trustworthy.

3. **Idea 2 (BIS-burst-onset MAP threshold)** — real mechanistic appeal
   (individualized, cuff-derived autoregulation surrogate without needing
   scarce NIRS) but ranks third because (a) it sits closer to an existing,
   well-established adjacent construct (MAPopt/BISopt/COx) and needs careful
   argument to avoid looking like a re-skin, and (b) anesthetic-depth
   confounding of burst suppression is a serious, well-documented threat that
   could swallow the whole effect if not rigorously conditioned on MAC/
   end-tidal agent concentration. Also has the smallest feasible cohort if
   restricted to the raw-EEG-waveform subgroup.

4. **Idea 4 (capnogram-ABP phase-drift)** — included and ranked last,
   honestly, because it sits closest to the named PPV/SVV space (the
   distinguishing "trajectory of phase, not magnitude" framing is real but
   thinner than the other three), the mechanistic outcome story is the least
   developed, and ventilation-mode/artifact constraints shrink the usable
   window more than the other constructs. Worth keeping on the list as a
   smaller follow-on analysis once the data-engineering pipeline for Idea 1
   (which also needs clean ABP waveform extraction) already exists, rather
   than as a standalone first project.
