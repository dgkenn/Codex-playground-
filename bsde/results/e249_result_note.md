# E249 — E248's gates completed. All four pass; the verdict is **(c) LEAKAGE**.

*2026-08-07. `bsde/src/bsde/experiments/e249_e248_gate_completion.py`, output
`results/e249_gate_completion.json`. Every threshold is transcribed unchanged from E248's docstring.*

---

## 0. The ordering fact, first

**P1 was seen before this file was written.** E248 computed its leakage table, and only afterwards did a
grep establish that P2, G1 and G3 were never implemented. Three things bound what that can have
contaminated, and they are checkable from the artefacts:

* **No threshold here is new.** G1's "half the candidates, 0.10 above their own null", G3's
  both-directions requirement, G4's 300 / 15, G2's comparison against the median candidate, and all four
  verdict branches are E248's, verbatim. Rule 58 forbids *revising* a gate after it fires; this one never
  fired.
* **G1 and G3 can only withdraw P1's licence, never grant it.** G1 asks whether the ventilation
  transition is legible at all — a property of the state axis, not of the arm contrast. G3 asks whether
  the P1 path detects a planted signal and rejects a planted null.
* **P1 was not recomputed.** Holm is applied to the p-values already in `e248_agent_leakage.json`.

## 1. P2 — the state axis is emphatically alive

Signed mean of `AUC(after vs before) − 0.5` across 2,573 patients about the **recovery** landmark. Signed,
not folded, because `|AUC−0.5|` is biased upward under the null (rule 46) and folding per patient would
manufacture legibility from noise at this n.

| candidate | signed mean | margin over null |
|---|---|---|
| `whole_head_exponent` | **−0.3629** | +0.3578 |
| `exponent_high` | −0.3587 | +0.3536 |
| `emg_beta_gamma_fraction` | +0.3386 | +0.3335 |
| `spectral_edge_95` | +0.3260 | +0.3209 |
| `multiscale_entropy_slope` | −0.3161 | +0.3110 |
| `critical_slowing_ar1` | −0.2296 | +0.2245 |
| `relative_alpha_power` | −0.2287 | +0.2236 |
| `emg_index` | +0.1808 | +0.1757 |

Null 95th ≈ 0.0051 throughout. **The directions are physiologically right and were not fitted**: the
aperiodic exponent flattens after the return of spontaneous breathing, spectral edge and entropy rise,
alpha falls. That is a recovery signature, recovered by an estimator told nothing about anaesthesia.

**The analytic null is checked, not assumed.** Against a 200-draw within-patient permutation:
0.00509 / 0.00509 / 0.00509 analytic against 0.00460 / 0.00590 / 0.00537 empirical on the three
candidates tested. Same move E248 made for P1, same agreement.

**Muscle tracks the transition too, and that is expected rather than a defect.** `emg_index` and
`emg_beta_gamma_fraction` are among the strongest state trackers, because the transition *is* partly a
muscle event — the patient starts breathing. **This does not contaminate P1**, which is a between-arm
contrast at matched state: `emg_index` sits at its null in all three arm pairs. The two facts are about
different comparisons and both belong in a write-up.

## 2. Gates — all four pass

| gate | result |
|---|---|
| **G1** phenomenon exists | **PASS** — 14 of 19 candidates ≥ 0.10 above their own null (needed 9.5) |
| **G2** nuisance placebo (the gate E154 failed) | **PASS** — every nuisance below the median candidate in all three pairs; worst `bmi` 0.0505 against 0.0758 |
| **G3** capability, both directions | **PASS** — planted positive detected at 0.4979–0.5000 against nulls of 0.025–0.034; planted negative at 0.0052–0.0163, below its null in all three pairs |
| **G4** support | **PASS** — smaller arms 412 / 903 / 412, all ≥ 300 |

**G3's rule-77 check ran before the control was used**: `corr(arm, negative control) = −0.0211`,
`corr(arm, positive control) = +0.9651`. E173's negative control was built to be independent and was not;
this one is measured.

**G1 was shown able to fail before it was believed.** Under the smoke run — before/after permuted within
patient — every candidate's margin goes negative and G1 returns **0 of 19, FAIL**. A gate that passes on
real data and fails on permuted data is a gate (rules 40, 81).

## 3. Holm on P1, and the verdict

| pair | candidates with Holm-adjusted p < 0.05 |
|---|---|
| sevo vs des | 11 of 19 |
| sevo vs ppf | 17 of 19 |
| des vs ppf | 14 of 19 |

**VERDICT: (c) LEAKAGE.** Frontal EEG measures carry resolvable anaesthetic-agent identity at a
patient-level permutation floor of 0.023–0.034, with maxima of 0.1442 / 0.2059 / 0.2922 — four to nine
times the floor, surviving Holm across candidates, with nuisance variables an order below and the
state axis independently established as alive.

E248's own framing of what this means, unchanged: *"a quantified criticism of every 'drug-independent'
estimator, Ramaswamy 2019's included."*

### 3.1 READ THE CHALLENGE STATEMENT BEFORE READING THIS AS A WIN — rule 95, and the ledger printed it

Registering E249 made `registry_ledger` echo Challenge A verbatim, which is what that anchor exists for:

> **A: "predicts loss and recovery across anaesthetics while MINIMISING drug-identification
> information"**

**Leakage is the quantity Challenge A asks a candidate to MINIMISE.** So against the briefed acceptance
criterion, a large, Holm-surviving, nuisance-free leakage value is **a disqualifier for every candidate in
this panel**, not a success for the programme. Eleven, seventeen and fourteen of nineteen candidates fail
the minimisation half of Challenge A on this deposit.

Rule 95 records that this project has already made exactly this error once — *"an entire session was spent
measuring how much drug-identification information the panel carries — the quantity A asks a candidate to
MINIMISE — and reporting a large value as a finding rather than as a disqualifier."* The result below is
worth reporting as a **measurement**, which is what E248 registered it as and the only thing its own
literature check found unclaimed. It is not worth reporting as progress on Challenge A.

**Both sentences are true and the order matters.** The measurement is novel: no published work quotes a
leakage value against a null, and the floor here is an order below anything this project could reach
before. And the panel does not satisfy Challenge A. A write-up that states the first without the second
is the drift rule 95 was written to stop.

## 4. Scope, and it is not a limitations paragraph

* **The state label is the AIRWAY RECORD** — measured respiratory rate against the ventilator's set rate.
  A **brainstem behavioural output, not consciousness.** This belongs in the first result clause.
* **Recovery only.** `rec_ok` holds in 2,592 cases and `loss_ok` in 110. The 16 loss-only cases are
  reported separately and never pooled: at loss the transition runs the other way.
* **`uce_v1` cannot be computed here**, with four other connectivity/spatial measures — all-NaN on two
  frontal channels in a 10 s window. E249 says nothing about the project's flagship candidate.
* **The cohort exclusion is mildly one-sided.** 2,930 landmarked cases → 2,600 with any window → 2,589
  after `MIN_WIN`. So **330 cases have no usable window at all** and only **11** fail the support
  criterion. By arm the total drop runs **sevo 13.57 % / des 10.43 % / ppf 9.34 %**. The file prints
  "even across arms" against a 0.05 spread threshold **invented for the occasion** — rule 63 — and the
  three rates are the honest report. Whether sevoflurane cases lose windows for a reason that also moves
  the candidates is untested.

## 5. What a successor owes

1. **The loss landmark at usable scale.** 110 cases is not enough, and the 120 s sustain is not to be
   re-tuned to manufacture more (rule 58). A separately-derived loss rule is the successor.
2. **Test the 330-case coverage gap for arm-relatedness properly**, rather than against an invented
   spread threshold.
3. **Do not re-run P1.** It is computed, its null is calibrated, and re-running it now would invite
   exactly the suspicion §0 exists to bound.
