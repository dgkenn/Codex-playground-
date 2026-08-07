# Anaesthetic-agent identity in frontal EEG is state-dependent: measuring near emergence understates it about fivefold

**Draft, 2026-08-07.** Written to what the evidence supports. Two blocking gaps are stated in §7 and
neither is closable in the analysis environment; **this draft should not be submitted until §7.1 and
§7.2 are done.**

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
* **The effect is carried entirely by volatile-versus-propofol.** Removing propofol collapses the
  gradient to −0.0086, while removing either volatile leaves it intact. Between two volatiles leakage
  sits at 0.05–0.12 everywhere, so this may be a floor effect — but the claim must name the contrast.

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

## 7. **BLOCKING GAPS — do not submit before these are closed**

### 7.1 The circularity objection is unresolved

Depth is indexed by BIS, which is computed from the same EEG as the candidates. Two attempts to control
for this failed:

* stratifying on a muscle channel instead reproduced **56 %** of the gradient — but muscle tone is itself
  depth-related, so the control was never independent;
* stratifying on the anaesthesia machine's own drug record (`Primus/MAC`, `Orchestra/PPF20_CE`, 100 %
  coverage) produced a gradient in the right direction (median ρ = +0.90, p = 0.0250) — **but that axis
  failed its own pre-registered validity check**, correlating with BIS at only −0.05 pooled
  (sevo −0.215, des −0.016, ppf +0.082). By the registration's own rule that result is uninterpretable
  whichever way it came out, and it is not used.

**What would close it:** a depth anchor that is neither EEG-derived nor a drug concentration — a
behavioural or reflex scale. DOSE-I (Zenodo 18483292, open) ships per-second MOAA/S in 171 recordings. It
is propofol-only so it cannot measure leakage, but it can test whether the BIS-indexed gradient survives
a behaviourally-defined depth axis, which is the transportable half of the objection.

### 7.2 Novelty is unverified

PubMed returns a small literature: **4 records** for `"drug-independent" AND electroencephalography AND
anesthesia` (PMIDs **38157438, 31326088, 10965721, 10939694**) and **4** for
`propofol AND sevoflurane AND EEG AND "depth of anesthesia" AND (classification OR discrimination OR
identification)` (**28574372, 23567809, 11759923, 11171465**), plus 7 for a broader depth-dependence
query (**40638527, 40113116, 35404821, 34517477, 20051218, 15816591, 12885180**). One of them —
31326088, Ramaswamy 2019 — is the known incumbent for the state-tracking arm.

**None was verified**, because the analysis environment's PubMed metadata tools require interactive
approval. Rules 25 and 39 forbid citing an unverified record, and a fetch-tool summary is not
verification. **Someone must read those ≤ 15 papers before any novelty claim is made.**

### 7.3 Weaker, non-blocking

* The within-patient dose-response returned null (0 of 18), but its estimator is a per-patient ratio with
  a near-zero denominator guarded only at 1 percentile point, so the null may be the statistic. The
  successor is a regression slope, not a re-run with a different guard.
* A second deposit pairing raw EEG with two mechanistically distinct agents would answer §4's
  volatile-only limitation. None is public; the Turku/Kallionpää cohort (PMID 32773216, 47 volunteers,
  dexmedetomidine vs propofol, within-subject loss and return at constant dosing) is the request target.

## 8. Honest positioning

With §7.1 and §7.2 closed, this is a **solid specialist methods paper** — a cautionary result for
anaesthesia EEG and for anyone building drug-invariant depth indices. It is **not**, on current evidence,
a high-impact general-audience paper: it is one deposit, one drug-class contrast, two frontal channels,
and a behavioural label that is explicitly not consciousness. Claiming more than that would be the error
this project's own record documents repeatedly.

**What would make it high impact** is a different paper: the same state-dependence demonstrated across
two or more mechanistically distinct agent pairs, on a behavioural depth axis, in more than one deposit,
with the invariance methods of the domain-adversarial literature shown to inherit the same flaw. Each of
those is an acquisition problem, not an analysis problem.
