# Consolidation — E139 to E162, and three things this project believed that are now false

*2026-08-01. Twenty-four registered experiments in one session. Every number here is from this
repository's own runs and is named with the experiment that produced it. Written to the ten-result cadence
in `CLAUDE.md`, which says stop generating and re-read the whole record.*

---

## The short version

**Three standing beliefs were overturned, and in each case the thing that overturned them was a control,
not a new idea.**

| what the project believed | what it is | how it fell |
|---|---|---|
| E36's phase/amplitude split: phase measures leak little drug identity | **absence of power** | arm is nested in patient — 15 units, not 115 blocks (E142) |
| "Four failures of the same shape are a result about the question" — Challenge C's increment designs don't work | **the instrument was blind** | it detects 0 % of a ρ = 0.35 effect (E146); eleven candidates add once it is fixed (E150) |
| Transport succeeds when the construct matches and fails when it does not | **refuted on its first forward test** | the DOSE-I ladder reproduces to within 0.01 in the ICU (E160, E162) |

And one thing the project did not believe and should: **most of the frontal amplitude family identifies
which anaesthetic is running**, at matched state, on two continents (E156 → E161).

---

## 1. The instrument, which decided eleven results

`oob_regression_increment`'s bootstrap tail fraction was used as a p-value across this project. **E146**
measured it against a closed-form partial-correlation test on synthetic data:

| n subjects | rows each | ρ_partial | OOB detects | oracle detects |
|---|---|---|---|---|
| 60 | 1 | 0.35 | **0.00 %** | 88.33 % |
| 100 | 1 | 0.50 | 38.33 % | 100.00 % |
| 100 | 3 | 0.35 | 66.67 % | 100.00 % |

with a false-positive rate of **0.000** at ρ = 0. It is blind, not conservative — the bootstrap's spread
is resample-to-resample variability, not the sampling distribution of the increment. **E147** built and
validated `permutation_increment` (cross-fitted, cluster-permutation null): calibrated at **0.0333**
against a two-sided bar where 0.000 *fails*, and retaining **86 %** of oracle power. It loses to the old
test in 2 of 24 live cells, which is recorded rather than smoothed over.

**Everything decided by the old instrument means "we could not have seen it", not "it is not there"**
(rule 31). Nine rows still await re-derivation: E26, E27, E34, E37, E58, E99, E130, E133, E134.

---

## 2. Challenge A — the news is bad, and it is finally solid

**The single statistic was computed for the first time** (E139): `Λ = state legibility − drug-identity
legibility`. It failed its own placebo — recording quality identified the agent at 0.2565 on the Krause
deposit — and chasing that produced **E142**, which is the durable result: arm is nested in patient, so
enumerating all C(15,7) = 6,435 labellings exactly leaves **2 of 12** features clearing the null, the
null's mean 95th percentile at **0.2791**, and row-level p-values inflated **178×**. E36's family gap of
+0.0913 has exact p = 0.0914. Three of four phase features have p > 0.20: their celebrated low leakage is
absence of power. E36's 495-partition test is *not* retracted — it asked a different question correctly.

**Then the agent signature, twice.** On the MGH OR cohort (E154–E156), after a nuisance gate caught
recording duration identifying the agent at **0.3771** (sevoflurane cases run nearly twice as long) and a
fixed-window summary plus duration weighting removed it, two features separated the arms with the
directions the anaesthesia literature predicts. **E161 replicated both on VitalDB**, where the agent
contrast is real (43 propofol-alone against 69 sevoflurane-alone; MGH had *one* sevoflurane case) and age,
sex, ASA and BMI are recorded and weighted out:

| | weighted \|AUC−0.5\| | null p95 | Holm p | signed AUC(sevo) | predicted |
|---|---|---|---|---|---|
| `relative_theta_power` | 0.3263 | 0.1013 | 0.0000 | **0.8022** | higher ✓ |
| `alpha_peak_hz` | 0.2990 | 0.1078 | 0.0000 | **0.1935** | lower ✓ |

`lempel_ziv`, `exponent_low`, `whole_head_exponent`, `relative_alpha_power` and `spectral_edge_95` clear
too. **Most of the amplitude family leaks agent identity**, which bounds Challenge A far harder than two
features would. And `alpha_peak_hz` is *also* E153's only behavioural-threshold survivor — a good state
marker and a bad Challenge A candidate, now supported on both halves.

**The recovery clause remains confined to ten subjects.** The MGH volunteers are the only behavioural
LOC/ROC data reachable; in **0 of 44** OR cases is a conscious epoch adjacent to an unconscious one
(median gap 286 epochs), and ds004541 has 7 subjects. Three landmark designs (E148, E151, E152) were each
killed by their own control before E153 left one weak survivor with sign counts at chance.

---

## 3. Challenge C — the founding negative is withdrawn, and eleven numbers beat a CNN

**E150** re-ran E84 with the calibrated instrument, on E84's own cohort and constants, with a measured
detectability floor of **0.05** (100 % detection at 0.10). Eleven of 27 candidates add to the validated
PE31 incumbent — `relative_alpha_power` −0.0351, `multiscale_entropy_slope` −0.0319, `bis_rbr` −0.0288,
`emg_index` −0.0248 and seven more, no placebo reaching the corrected bar. **E84's negative is withdrawn
and QUEUE.md's "four failures of the same shape are a result about the question" is void.** The magnitude
caveat travels with it: the increments run −0.0015 to −0.0351, so *"nothing adds" was wrong and most of
what adds is small.*

**E159** put eleven hand-built spectral features against the deposit's own published 1,280-dimensional
MobileNet representation, reduced exactly as its paper specifies, on 46,948 windows at 100 % grid
alignment with subjects held out whole:

| | out-of-fold AUC |
|---|---|
| published CNN, 10 PCs | 0.8092 |
| **eleven hand-built spectral features** | **0.9426** |
| both | 0.9485 |

Spectrum over CNN **−0.12980**; CNN over spectrum **−0.00296**. Both detectable at that n; **the spectrum
adds 44× more.** All gates clean, including a leakage gate judged against its *measured* null.

---

## 4. Challenge D — the programme's central methodological claim does not survive

`PROGRAMME_ROADMAP.md` states: *"transport succeeds when the construct matches and fails when it does
not, and construct match is specifiable in advance"*, and flags it as a retrodiction over four
observations. `CHALLENGE_D_PREREGISTRATION.md` committed the forward prediction on 2026-08-03 while the
extraction was still streaming: **out-of-bag ρ below +0.25**, five of six axes mismatched.

| rung | MIMIC-IV (ICU, multi-drug infusion, RASS, days) | DOSE-I (endoscopy, bolus propofol, MOAA/S, minutes) |
|---|---|---|
| L0 cumulative dose | +0.1872 | +0.1755 |
| L2 + kinetic basis | **+0.4293** | +0.4263 |
| L0 → L2 gain | +0.2421 | +0.2508 |

Both predictions fail. Two alternatives were tested before the verdict was allowed to stand. **Time is
refuted** — `hours_in` alone reaches +0.0695. **Clinical intent looked decisive and was not**: the
most-recent goal correlates with the *previous* RASS in the same stay at **+0.5549**, so it is a collider,
and conditioning on it drags the cumulative-dose rung from +0.19 to +0.55 by importing the outcome.
Adjusting instead for the stay's **first** charted goal — near pre-exposure — leaves the ladder unchanged
at L2 **+0.4289**, gain +0.2330 (E162).

**So transport is intact and the rule is refuted.** E160's own "[+0.16, +0.43], undecidable" reading is
withdrawn: its lower endpoint was the collider artefact.

---

## 5. What bounds the programme now

**No public disorders-of-consciousness EEG deposit exists.** All **1,834** OpenNeuro datasets were
enumerated through the API and parsed directly; 517 carry EEG or iEEG; 36 match an eighteen-term keyword
set; **none is a DoC cohort**. The three anaesthesia deposits are two already in use and one with a single
subject. So **BATH-01632** (Challenge B's real target) and **Turku/Kallionpää** (Challenge A's two-agent
recovery clause) are not options among several — they are the only routes, and both are outstanding
requests.

**Challenge B's null is now interpretable rather than empty.** With the calibrated instrument the
incumbent is alive on eegmmidb (p = 0.034) and **0 of 32 candidates add**. The withdrawal of
`relative_alpha_power` that E145 wanted to issue is not issued. Its one apparent winner, `mean_triallength`,
was the outcome renamed — trials end on target-hit and otherwise time out, so length is mechanically the
inverse of accuracy (ρ = −0.3492).

---

## 6. New error-catalogue rules from this session

**69** nested exposure ⇒ the cluster is the unit; row-level nulls inflated significance 178× here.
**70** a candidate list of "every numeric column" contains re-descriptions of the outcome.
**71** a verdict must check the gate on the arm its winner came from.
**72** measure a control's null under the exact resampling scheme; a cross-validated pooled AUC under
within-subject permutation is centred at **0.4463**, not 0.5, and 54 % of draws fall outside a nominal
[0.45, 0.55] gate.

Five further gate-mechanics defects were found and fixed in place this session — a gate tested against a
degenerate self-null (E140, E155), a capability probe below the noise floor (E155, E156, and carried into
E157 after being diagnosed), a one-draw test of a rate (E158), an all-NaN column scored at p = 0.0000
(E157), and a verdict branch keyed on significance while ignoring a 44× difference in magnitude (E158,
disclosed before E159 ran).

---

## 7. What to do next, in order

1. **Re-derive the nine remaining increment-decided rows** with `permutation_increment`. E150 shows the
   verdicts can move; leaving them is knowingly carrying results from a blind instrument.
2. **Chase BATH-01632 and Turku/Kallionpää.** The survey establishes there is no substitute. Add a request
   for the MGH volunteer *response-probability* time series, which would turn a binary label into a graded
   behavioural target on the only cohort with behavioural LOC and ROC.
3. **Rewrite `PROGRAMME_ROADMAP.md`'s Challenge D section.** Its central claim has been refuted by its own
   pre-registered test and the document still asserts it.
4. **Write up E159.** Eleven interpretable numbers beating a published learned representation on its own
   deposit is a result the wedge application can use, and it is finished.
