# Prospective trial protocol — does adding an arterial line in gray-zone surgery improve outcomes?

**Why this is the central deliverable.** The observational analyses (docs 21–23) establish the *measurement*
finding (C8) but cannot establish that *placing a line* helps: confounding by indication, verification/selection
bias (outcomes observable only in already-lined patients), and realized-duration leakage make the observational
"tool" hypothesis-generating at best (doc 23 §5). Only a randomized trial in the **un-lined gray-zone population**,
using **anticipated** (not realized) case features and a **non-circular hard outcome**, can validate a decision
rule. This protocol is that trial.

## 1. Question (PICO)
- **P:** Adults undergoing elective moderate–major non-cardiac, non-neuro surgery, ASA II–III, **without an
  established arterial-line indication** (i.e. the true gray zone — no Layer-1/2 trigger from doc 23), anticipated
  duration ≥ 2 h, in whom the anesthesiologist is in genuine equipoise about arterial monitoring.
- **I:** Pre-operative placement of a radial arterial line + protocolized hypotension management (treat MAP < 65).
- **C:** Usual-care oscillometric cuff monitoring (cycled ≤ 3–5 min per standard) + the same MAP < 65 treatment
  target. (A 3rd arm — cuff cycled ≤ 2–3 min + treat at **MAP < 70**, the C8 detection correction, no line — tests
  the model-free correction against both.)
- **O:** see §3.

## 2. Design
Pragmatic, multi-center, parallel-group RCT; 1:1:1 (or 1:1 if the MAP<70 arm is deferred to a factorial
follow-up). Central randomization, stratified by site + surgery category. Monitoring cannot be blinded; **outcome
adjudication is blinded** and all endpoints are arm-symmetric (measured identically regardless of monitor).

## 3. Endpoints (non-circularity is the whole point)
- **Primary — hard, arm-symmetric:** postoperative **KDIGO AKI within 7 days** (creatinine-based; measured the
  same in both arms). *Cuff-missed hypotension is explicitly NOT the primary* — it is unobservable in the cuff
  arm and would be circular.
- **Key secondary:** composite organ injury (AKI **or** MINS by postop troponin), 30-day mortality,
  hyperlactatemia, ICU admission, hypotension-treatment latency, total hypotension burden where measurable.
- **Mechanistic (art arm only, descriptive):** quantify cuff-missed hypotension actually surfaced (links back to
  C8), vasopressor-timing improvement (tests the treatment-gap mechanism prospectively).

## 3a. Two-stage design (revised after review — test the cheap, non-invasive question first)
A reviewer rightly noted the tension: if the **model-free MAP<70 + fast-cycling correction** captures much of the
benefit non-invasively, it is unethical and inefficient to gate the science behind a large invasive arterial-line
trial. Revised plan:
- **Stage 1 (lead-in, cluster-randomized, cheap/fast):** sites/lists randomized to **cuff cycled ≤2–3 min +
  treat MAP<70** vs usual care (cuff per-standard + MAP<65). Tests the most actionable, lowest-risk question
  first. This is now a **co-primary** aim, not an "optional third arm."
- **Stage 2 (individual RCT, invasive):** arterial line + MAP<65 vs usual cuff + MAP<65, in the gray-zone
  population, for the incremental value of direct monitoring beyond the Stage-1 correction.

## 4. Sample size (with clustering)
Gray-zone major-surgery AKI baseline ≈ 12%. To detect an absolute reduction to 8.5% (≈30% relative; INPRESS-scale
organ-dysfunction effect), α 0.05 two-sided, power 90%: ≈ **1,500–1,900 per arm** *before clustering*. The
pragmatic multi-site design induces clustering: with intraclass correlation ρ≈0.02 and ~50 patients/site the
design effect ≈ 1+(50−1)·0.02 ≈ 2.0, so the **cluster-randomized Stage-1** needs ≈ **3,000–3,800 per arm**
(individually-randomized Stage-2 is less inflated). Full power table across ρ ∈ {0.01,0.02,0.05} and true effect
∈ {2,3,4 absolute points} is pre-specified; an adaptive futility interim is included. The point-estimate effect
is *not* imported from the observational attenuation ORs (which are subject to their own caveats) — it is set to
the minimum clinically important difference.

## 5. Analysis
Intention-to-treat primary; per-protocol + CACE (complier-average) sensitivity for crossover (some control
patients will get rescue lines — a strength, mirroring practice). Pre-registered SAP; subgroup HTE by the doc-23
severity factors is **exploratory** (the observational score's only legitimate role — generating the subgroup
hypotheses this trial tests). E-value not needed (randomized).

## 6. Relationship to prior trials — explicit contrast (so it is not misread as "another INPRESS")
| dimension | INPRESS (Futier 2017) | GUARDIAN / POISE-3 BP | **This trial** |
|---|---|---|---|
| Population | already arterial-lined, high-risk | mixed, BP-target focus | **un-lined gray-zone (no established indication)** |
| What varies | BP *target* (individualized vs standard) | BP target / med management | **monitoring modality / the line decision** |
| Comparator | standard target, same monitor | usual BP mgmt | usual cuff, **same** MAP target |
| Outcome | organ dysfunction (SIRS composite) | AKI/MI/mortality | **KDIGO AKI (arm-symmetric)** |
| Question | *how low to treat* | *how to manage BP* | ***whether to see the BP the cuff hides*** |

INPRESS varied the *target* in patients who already had the arterial signal; this trial asks whether providing
that signal at all — in patients who currently would not get it — changes outcomes. It directly operationalizes
C8: the cuff misses the very hypotension INPRESS-style management depends on detecting.
- **GUARDIAN / POISE-3 BP substudies** inform the treatment target, not the monitoring-modality decision.

## 7. Feasibility / equipoise
The documented 30–45% practice variation in the ASA-2-major / ASA-3-moderate gray zone (doc 21 §d) is direct
evidence of genuine equipoise — the ethical precondition for randomization is already met by the fact that
clinicians disagree today. A pilot internal-feasibility phase (site training, crossover-rate estimate,
AKI-ascertainment QC) precedes full enrollment.
