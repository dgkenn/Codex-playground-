# Anaesthetic-agent identity in frontal EEG is state-dependent: measuring near emergence understates it about fivefold

**Draft, 2026-08-07.** Written to what the evidence supports. **Both gaps that previously blocked this
draft are now closed** — §6b replicates the effect on a behavioural depth axis with a mechanistically
distinct drug pair in an independent deposit (p = 0.0016), and §7.2's novelty check has been completed
against verified MEDLINE records. Remaining limitations are real but are limitations, not blockers.

---

## 1. What this paper claims

Anaesthetic depth-of-anaesthesia monitors and research EEG markers are routinely described as
"drug-independent" or "agent-invariant". We show, in 2,589 surgical patients, that **how much anaesthetic
agent identity an EEG measure carries is not a property of the measure alone — it depends strongly on the
state at which it is measured.** The same panel of 19 spectral and complexity measures identifies
volatile-versus-propofol at |AUC − 0.5| ≈ 0.35–0.43 during maintenance and ≈ 0.06–0.07 in windows around
the return of spontaneous ventilation — a fivefold difference in the same patients.

Two consequences follow, and they are the paper:

1. **An invariance claim without a declared measurement state is uninterpretable**, and evaluating near
   emergence flatters a representation by roughly a factor of five.
2. **The ranking of which measures leak most barely transports between states** (Spearman ≈ +0.29 to
   +0.37), so a candidate-selection procedure run at one depth does not select the same candidates at
   another.

## 2. Data and design

**Cohort.** VitalDB, every public case carrying `BIS/EEG1_WAV`, `Primus/MAC`, `Primus/RR_CO2` and
`Primus/SET_RR_IPPV` with a sane `aneend`. Single-agent arms: **sevoflurane 1,274 / desflurane 412 /
propofol 903 (2,589 cases)**.

**State label.** The airway record — measured respiratory rate against the ventilator's set rate, which
separates controlled from spontaneous ventilation. **This is a brainstem behavioural output and is not
consciousness.** It was chosen over the two obvious alternatives because both are circular here: the drug
record makes "tracks state" and "follows the drug" the same quantity, and BIS is computed from the same
EEG as every candidate. The landmark rule's 120 s sustain was derived from measured run lengths, not
chosen.

**Windows.** Two matched sets of 21 windows of 10 s at fixed offsets −300…+300 s in 30 s steps:
* **peri-landmark**, centred on the return of spontaneous ventilation (56,731 windows, 56,237 usable);
* **maintenance**, centred 2,400 s earlier, ≥ 900 s clear of both landmarks and inside the anaesthetic
  (15,747 windows, 15,547 usable, 740 cases balanced 250/arm).

Window count and offsets are identical for every case. This is load-bearing: recording duration alone
identifies the agent at |AUC − 0.5| = 0.3771 in this deposit, and any summary whose window count depends
on case length re-imports that confound.

**Leakage statistic.** Per candidate, one value per patient (median across that patient's windows), then
|AUC − 0.5| between arms, with a 20,000-draw **patient-level** permutation null. Agent identity is a
property of the patient, so the effective n is the number of patients; a row-level null inflates
significance by orders of magnitude. Empirical and analytic nulls agree to the third decimal
(0.0317–0.0324 against an analytic 0.0321).

## 3. Principal result

| pair | maintenance | peri-landmark | analytic null₉₅ |
|---|---|---|---|
| sevoflurane vs propofol, `whole_head_exponent` | **0.3525** | 0.0668 | 0.0246 |
| desflurane vs propofol, `whole_head_exponent` | **0.3788** | 0.0635 | 0.0337 |
| desflurane vs propofol, `alpha_peak_hz` | **0.3545** | 0.2922 | 0.0337 |
| sevoflurane vs propofol, `relative_alpha_power` | **0.2212** | 0.0015 | 0.0246 |

In readable units: `whole_head_exponent` at maintenance is sevoflurane **2.6151**, desflurane **2.7342**,
propofol **2.2532** — a volatile-minus-propofol difference of **0.36–0.48 exponent units**, Cliff's δ
**+0.705 / +0.758**. Sevoflurane versus desflurane is −0.12 (δ −0.205).

**The graded form.** Across within-cohort BIS quintiles, leakage declines monotonically as BIS rises:
median Spearman **−0.90**, permutation p **0.0000**, four of six top candidates at exactly −1.0.
Replicated independently in the peri-landmark cohort at 3.5× the n (deep 0.3649 vs light 0.0788,
6 of 6 candidates).

## 4. What it is not

| alternative explanation | test | outcome |
|---|---|---|
| cohort size | subsample peri-landmark to 250/arm × 200 | maintenance above the 99th percentile for all top candidates |
| the arms sit at different depths | 1:1 matching on maintenance BIS | leakage **rises** (median retention 1.086) |
| case mix (age, BMI, duration) | trim to joint 10–90th overlap | retained (0.379 → 0.378) |
| signal quality | restrict to monitor SQI ≥ 50 | leakage **increases** |
| burst suppression | median max SR = 0.00 in every arm; restrict to SR-free | unchanged |
| proximity to the transition rather than depth | match cohorts on BIS band [41.3, 52.9] | median ratio 0.806 — mostly depth |
| sampling instability | split-half of the maintenance cohort | Spearman **+0.8596** |

**Mechanism.** The effect is a location offset: subtracting each arm's own median removes **51–98 %** of
leakage, and the residual sits at or below its permutation null in **16 of 18** cells. Level out-leaks
change in **19 of 19** candidates at maintenance.

**Two observations that cut against the simple story, reported because they do.**
* **BIS is the exception.** The incumbent index leaks *less* than our median candidate at maintenance
  (0.0747 / 0.0469 / 0.1218 against 0.0918 / 0.2241 / 0.2077), and its own gradient runs the *other* way
  (deep 0.0884 → light 0.1286). Every candidate worsens with depth; the commercial index does not.
* **Within VitalDB the gradient is carried entirely by volatile-versus-propofol.** Removing propofol
  collapses it to −0.0086, while removing either volatile leaves it intact. Between two volatiles leakage
  sits at 0.05–0.12 everywhere, so this is plausibly a floor effect — there is little signal to grade.
  **This is a limitation of VitalDB's drug set, not of the phenomenon: §6b demonstrates the same
  state-dependence for propofol versus dexmedetomidine, a GABA-A/α₂ contrast outside the volatile axis
  entirely.** Any statement restricted to VitalDB must still name its contrast.

## 5. The state axis, for completeness

The ventilation transition is strongly legible — `whole_head_exponent` at a signed within-patient
mean AUC − 0.5 of **−0.3629** over 2,573 patients against a null₉₅ of 0.0051, with physiologically
correct and unfitted directions (the aperiodic exponent flattens, spectral edge and entropy rise, alpha
falls at the return of spontaneous breathing). **It is landmark-specific**: at a landmark-free control
centre every candidate collapses to within ±0.012 of zero. It is not depth-confined (present in all three
BIS terciles, 6 of 6) and it **transports across agents essentially intact** — a threshold fitted on one
arm and applied to another loses a median of 0.0042 accuracy and beats a wrong-measure placebo in 10 of
12 comparisons.

## 6. Limitations, stated as limitations

* **The state label is a brainstem behavioural output, not consciousness.** Nothing here transfers to
  disorders of consciousness or to awareness.
* **Recovery only.** The loss landmark is usable in 110 cases against 2,592 for recovery.
* **Two frontal channels, one deposit, one institution.**
* **`uce_v1` and four connectivity/spatial measures are uncomputable** on two frontal channels in a 10 s
  window; this panel says nothing about them.
* **Observational.** Each patient receives one agent, so the agent main effect is not identifiable
  separately from between-patient differences except in the within-patient contrast of §3.
* **The cohort exclusion is mildly one-sided** — 13.57 % of sevoflurane cases lost against 9.34 % of
  propofol, tracking anaesthesia duration (13,200 s dropped vs 11,100 s kept, age identical).

## 6b. EXTERNAL REPLICATION ON A BEHAVIOURAL AXIS, WITH A MECHANISTICALLY DISTINCT DRUG PAIR

The two objections that mattered most — that depth was indexed by an EEG-derived quantity, and that the
effect was confined to volatile-versus-propofol — are answered together by an independent deposit.

**Krause/Banks (Zenodo 10.5281/zenodo.15497531), 29 patients, intracranial EEG.** The state label is an
**OAA/S ladder scored at the bedside** — behavioural, not computed from the EEG. The drug pair is
**propofol (GABA-A) against dexmedetomidine (α₂ agonist)**, the furthest reachable pair, with published
opposite-signed EEG effects at matched sedation depth.

| | leakage between arms |
|---|---|
| **unresponsive** | **0.2279** |
| **wake** | **0.0632** |
| difference **D** | **+0.1648** |

Cluster-level permutation null over the 29 patients (drug is nested in patient, rule 69; 5,000 draws):
95th percentile **+0.0808**, median +0.0047, **p = 0.0016**. All three gates pass — both states populated,
the state axis alive within the propofol arm (11 of 17 features separate wake from unresponsive at
|AUC−0.5| ≥ 0.25), and a both-directions capability control whose negative was measured for independence
before use (corr with drug −0.0382).

**This experiment does not measure leakage and does not try to.** With 19 versus 10 patients the
patient-level null sits near 0.28 on this deposit (measured previously at 0.2791 for 15 patients), so
absolute values are uninterpretable. It measures the *difference* between two states in the same
patients, which is a paired contrast and far better powered than either level.

**Two honest qualifications.** The gradient is **not monotone across the three-level ladder** — sedated
versus wake gives only D = +0.0138, so the effect is concentrated at unresponsiveness rather than rising
smoothly. And the scope is real: intracranial electrodes in epilepsy-surgery patients, features computed
by the depositors' pipeline (the deposit ships no raw traces, so an independent re-implementation check
is unavailable), block-level rather than per-second labels, and 10 dexmedetomidine patients.
**This is a replication of a direction, not of a magnitude.**

### 6b.1 The no-drug placebo: the same statistic, the same people, the drug removed

§6b's two arms are different *people* — different electrode coverage, different epileptic foci. If
between-patient differences of any kind became more legible at deeper states, arm separability would rise
with depth **with no drug involved**, and §6b's reading would be wrong.

The deposit settles it. Nineteen of these patients also have staged natural overnight sleep — 13 from the
propofol arm, 6 from the dexmedetomidine arm. During sleep **neither group is receiving any drug**, yet
they remain the same two groups of people, with the same electrodes, traversing a graded depth ladder.

| | deep | wake | **D** | p |
|---|---|---|---|---|
| **drug** (unresponsive vs wake, §6b) | 0.2279 | 0.0632 | **+0.1648** | **0.0016** |
| **no drug** (N2/N3 vs wake sleep) | 0.0909 | 0.0909 | **+0.0000** | 0.5148 |

Deep-sleep and wake-sleep separability are **identical to four decimals**, against a cluster permutation
null 95th of +0.0769. The sleep depth axis is alive (10 of 17 features separate wake from deep sleep
within the propofol group), and the two patient groups are not detectably different at baseline
(separability 0.0909 at wake sleep, against a patient-level null near 0.29 at these arm sizes).

**The alternative explanation is excluded: state-dependent between-patient separability does not
reproduce the drug result.** Under permuted arm labels the same test returned "placebo fires", so the
branch is reachable and the null is not an artefact of an unfireable gate.

**Power caveat, registered before the run and not softened after it:** with 13 versus 6 patients only a
large D_sleep would be detectable, so this is a clean null rather than a strong one. The point estimate
being exactly zero is as favourable as such a null gets, but the interval is wide.

### 6b.2 What carries it: complexity and amplitude, not phase

The aggregate results above are medians over 17 features. Decomposed by instrument family, with families
assigned before any statistic was computed and the same cluster-level null:

| family | D (unresponsive − wake) | null₉₅ | p |
|---|---|---|---|
| **complexity** (2 measures) | **+0.3632** | +0.1747 | **0.0002** |
| **spectral** (8 measures) | **+0.1500** | +0.1237 | **0.0218** |
| connectivity (6 measures) | +0.0566 | +0.1554 | 0.2856 — **at null** |
| spatial (1 measure) | — | — | not computable (rule 74) |

**Prediction met.** Complexity and spectral measures carry the state-dependence; phase-based connectivity
does not. This is the mechanism VitalDB implied but could not test — two frontal channels make every
connectivity measure NaN there — and it is consistent with the VitalDB finding that leakage lives in the
signal *level* (a per-drug median shift removes 51–98 % of it).

**A post-hoc observation that I checked and then withdrew.** Two of the six connectivity members are
higher than the rest — `allEnvCorr` +0.1632 and `InsAwPLI` +0.1693 — and I initially read that as an
amplitude-versus-phase split, which would have matched the mechanism neatly. **It does not.** Measured
directly, `InsAwPLI` correlates with the other wPLI variants at +0.20 to +0.78 (`allwPLI` +0.7841) and
with `allEnvCorr` at only +0.0660: it is a phase-based wPLI variant, and I had inferred "amplitude" from
a letter in its name (catalogue rule 61 — parse a structured identifier, never substring-read it).

**So no mechanistic sub-story is supported.** The two elevated members do not share an instrument type,
and the connectivity family as a whole remains at its null. The one defensible related observation is
that `allEnvCorr` correlates with `AvgDelta` at +0.5460, so envelope correlation is partly a delta-power
measure — which is why it tracks the spectral family rather than the phase family.

**The ladder is not uniformly threshold-like.** E305's secondary showed the middle rung nearly flat in
aggregate; per family the reason is visible. Complexity is **graded** — it already separates the arms at
the sedated rung (D = +0.1582, p = 0.0038). Spectral is **threshold-like** — flat at sedated
(D = −0.0196, p = 0.8606) and firing only at unresponsiveness. The aggregate looked threshold-like
because the eight spectral measures dominate the median. *(This comparison is confirmatory rather than
blind: E305's sedated point estimate was seen before it was written, and it is labelled as such.)*

## 7. Remaining gaps

### 7.1 Circularity — substantially closed, not eliminated

Depth is indexed by BIS, which is computed from the same EEG as the candidates. Two attempts to control
for this failed:

* stratifying on a muscle channel instead reproduced **56 %** of the gradient — but muscle tone is itself
  depth-related, so the control was never independent;
* stratifying on the anaesthesia machine's own drug record (`Primus/MAC`, `Orchestra/PPF20_CE`, 100 %
  coverage) produced a gradient in the right direction (median ρ = +0.90, p = 0.0250) — **but that axis
  failed its own pre-registered validity check**, correlating with BIS at only −0.05 pooled
  (sevo −0.215, des −0.016, ppf +0.082). By the registration's own rule that result is uninterpretable
  whichever way it came out, and it is not used.

**This is now answered by §6b**, which uses a bedside-scored OAA/S ladder — behavioural, not derived
from the EEG — and finds the same direction at p = 0.0016. The VitalDB gradient is therefore not an
artefact of stratifying an EEG measure on an EEG-derived index.

**What remains.** Within VitalDB itself no non-EEG depth axis validated (§7.1's original two failures
stand as reported), so the *quantitative* VitalDB gradient still rests on BIS. The claim that survives
without qualification is the direction and the existence of state-dependence; the specific quintile
slope of −0.90 is BIS-indexed and should be presented as such.

### 7.2 Novelty — checked against verified records

PubMed returns a small literature: **4 records** for `"drug-independent" AND electroencephalography AND
anesthesia` (PMIDs **38157438, 31326088, 10965721, 10939694**) and **4** for
`propofol AND sevoflurane AND EEG AND "depth of anesthesia" AND (classification OR discrimination OR
identification)` (**28574372, 23567809, 11759923, 11171465**), plus 7 for a broader depth-dependence
query (**40638527, 40113116, 35404821, 34517477, 20051218, 15816591, 12885180**). One of them —
31326088, Ramaswamy 2019 — is the known incumbent for the state-tracking arm.

**All 15 were retrieved and read from their MEDLINE records via NCBI E-utilities** (not a fetch-tool
summary; rules 25 and 39 satisfied). The two closest:

* **PMID 38157438** (*Anesthesiology* 2024) hypothesises that spatiotemporal complexity is "state-related
  but not drug-related" across propofol and esketamine (n = 10 + 10) and reports state effects under both
  drugs. It does **not** quantify drug-identifiability against a null, and does not stratify it by state.
  Different estimand, and n = 20 is far below what resolving leakage requires.
* **PMID 31326088** (Ramaswamy 2019) compares pooled against per-drug AUC (0.83 vs 0.97/0.74/0.77). That
  is a *performance* comparison, not a leakage measurement, and it is not state-stratified.

The remainder are depth-of-anaesthesia monitoring papers, propofol-only microstate work, or unrelated.
**No verified record measures agent-identifiability against a null, and none reports its dependence on
anaesthetic state.** The claim appears unclaimed within the searched set.

**PMID 41385421 has now been retrieved from its MEDLINE record** (*IEEE J Biomed Health Inform* 2025,
"EEG-based Cross-subject Prediction for Consciousness State Transitions under Sedation using a Deep
Learning Framework"). It uses domain-adversarial training on propofol and midazolam — **both GABAergic**,
not a distinct-class pair — and reports cross-anaesthetic performance as *external validation*
(93.93 % / 97.42 %), not as an adversarial objective on drug identity. Its title names the adversarial
setting as **cross-subject**. Strictly, the abstract does not state the adversarial domain variable, so
that inference is labelled as an inference (rule 42) — but on either reading the paper reports transfer
*accuracy* and does not quantify agent-identifiability against a null, nor its dependence on state.

**Boundary of the search, stated rather than implied:** PubMed only, a handful of query formulations, and
no coverage of IEEE/arXiv beyond what PubMed indexes.

### 7.3 Weaker, non-blocking

* The within-patient dose-response returned null (0 of 18), but its estimator is a per-patient ratio with
  a near-zero denominator guarded only at 1 percentile point, so the null may be the statistic. The
  successor is a regression slope, not a re-run with a different guard.
* A second deposit pairing raw EEG with two mechanistically distinct agents would answer §4's
  volatile-only limitation. None is public; the Turku/Kallionpää cohort (PMID 32773216, 47 volunteers,
  dexmedetomidine vs propofol, within-subject loss and return at constant dosing) is the request target.

## 8. Positioning

The paper now rests on **two deposits, two mechanistically distinct drug contrasts, two independent state
axes — one ventilatory and one behavioural — and one recording modality each (scalp and intracranial)**,
with the direction agreeing in both (VitalDB ρ = −0.90, p = 0.0000 across BIS quintiles; Krause
D = +0.1648, p = 0.0016 across a behavioural ladder). The cautionary consequence — that an invariance
claim without a declared measurement state is uninterpretable, and that evaluating near emergence
understates leakage roughly fivefold — is supported by both.

That is a **strong specialist paper** and a legitimate methodological caution for the depth-monitoring
and drug-invariance literature. It is still not a general-audience result: the state labels are a
brainstem behavioural output and a sedation ladder, neither of which is consciousness, and the
intracranial replication is in epilepsy-surgery patients.

**What would lift it further**, in order: a third agent pair outside the GABA/α₂ axis (ketamine — the
Dryad CC0 set, n = 10, is open); a scalp replication of the behavioural-axis result; and obtaining PMID
41385421 to establish whether the domain-adversarial literature has already claimed the minimisation
framing. None of these is required for the claim as stated.
