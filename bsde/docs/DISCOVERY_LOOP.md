# DISCOVERY_LOOP.md — the loop, and the reason its termination condition is not "success"

*Written 2026-07-30, after thirteen registered designs produced two reportable verdicts.*

---

## 0. The bug this document exists to prevent

The natural specification for an autonomous research loop is **"keep going until it finds a solution."**
That specification is wrong here, and it is wrong in a way that would quietly undo everything the gates in
this repository were built to protect.

Of the thirteen designs registered so far, **eight were refused by their own machinery gates, blocked,
withdrawn by their own placebo, or closed by a pre-commitment.** A loop that halts on success will keep
varying designs until one passes — and because it halts, the eight failures never enter the denominator.
That is an unbounded, unreported search space. It violates two of the programme's ten constraints directly:
*never let the AI rewrite the hypothesis after seeing the test result*, and *report the size of the search
space*.

There is a sharper version of the problem. `verifier/multiplicity.py` corrects for looking at eighteen
candidates **inside** one experiment. A loop creates multiplicity **across** experiments, and until
`REGISTRATION_LEDGER.jsonl` existed, nothing counted it.

**So the termination condition is exhaustion, not success.** The loop runs until the queue is empty or the
budget is spent, and it reports what it did either way. A loop that ends with "thirteen designs, two
verdicts, one of them positive on one arm" is doing its job. A loop that ends with "found it!" after
silently discarding twelve attempts is not.

---

## 1. The cycle

Each iteration is one pass. **Most iterations will not produce a result, and that is the expected
behaviour, not a fault.**

| # | step | may be automated? | notes |
|---|---|---|---|
| 1 | **Literature → blocker** | yes | What does the field already know, and what does that make the *specific* blocker? Verified via NCBI E-utilities with `curl`, never WebFetch (rules 25, 39). |
| 2 | **Acquire** | yes | Find and ingest data addressing the named blocker. No inferential risk. |
| 2.5 | **Probe feasibility** | yes | `governance/feasibility.py`. Sentinels, artefact-tracking, exposure shape, within-subject variation, coverage, base rate — **from the label, exposure, artefact channels and clinical record only, never a candidate column**. Output pasted into the registration. See §2.5. |
| 3 | **Register** | **no — judgement** | Predictions, gates, placebo, falsification condition, **and the incumbent it must beat**. Written to a file and **committed before the data exists**. Append a row to the ledger in the same commit. |
| 3.5 | **Prove each gate can fail** | yes | For every gate in the registration, construct the input that *should* fail it and check that it does. `tests/test_new_gates_can_fail.py` is the pattern. See §2.6. |
| 4 | **Run once** | yes | Gates first. A failed gate ends the iteration. |
| 5 | **Record** | yes | Write the outcome into the experiment file *and* the ledger, including failures. Commit. |
| 6 | **Diagnose** | **no — the dangerous step** | See §2. |

Step 1 is the step this programme skipped for its first twelve designs, and it cost the most. Gugino 2001
(PMID 11517126) turned out to be a publication of Challenge A itself, found only after E30's sign reversal
forced a search. **Literature comes first, or the loop is shooting in the dark with excellent instruments.**

---

## 2. Step 6 is where a loop goes wrong, and the rule that contains it

A failed experiment may spawn a successor **only by changing the instrument** — the deposit, the label
source, the estimator, the contrast. It may **never** spawn a successor that changes the threshold, cohort,
horizon, or parameter that just failed.

The distinction is not a matter of taste and this repository contains worked examples of both:

* **Legitimate.** E21 (arms by charted time) → E22 (arms by depth index) → E25 (label moved off the EEG
  entirely, onto administered dose) → E29 (matched pairs) → E30 (a second deposit with no co-titrated
  opioid). Each changed *what was measured or where it came from*. Each is recorded in the ledger with
  `instrument_changed` filled in.
* **Refused.** E29's parameter sweep found exactly one of nine settings that cleared its opioid-holding
  gate, and it cleared it by halving the dose contrast. **The primary was not run in that cell**, and the
  refusal is written into the file. E27's `SR > 0` arm passed every gate and would have been reportable
  alone; it was not reported, because the registration required both thresholds. E31 missed its coverage
  floor by one patient and the floor was not moved.

Every successor row in the ledger carries `successor_of` and `instrument_changed`. **A successor that
cannot name the instrument it changed is the shape of a goalpost being moved, and it is visible in the
ledger as an empty field.** That is the audit.

---

## 2.5. The feasibility probe, and why it is not cheating

**Eight of the first thirteen designs died on machinery or coverage rather than on their hypothesis** — four
`gate_failed`, two `absent`, two `blocked`. Every one was computable in advance without touching a candidate
column:

| design | what killed it | how it was detectable in advance |
|---|---|---|
| E21 | `BIS/BIS` writes 0.0 with the sensor detached | one exact value held **49.1 %** of a continuous column |
| E22 | every BIS ≥ 80 window is facial EMG | P(label) rose **0.30 → 0.74** across artefact deciles |
| E27 | base rate 4.0 % against a 5 % floor | arithmetic on the label alone |
| E29 | within-pair opioid change is 104 % of chance | a median on two clinical columns |
| E31 | 19 patients against a floor of 20 | a count |
| E32 | low MAC tercile has median 0.00 | **53 %** of the exposure is exactly zero |

`feasibility.py` reproduces the first, second and sixth of those in seconds, on the real tables.

**Why this does not compromise the registration.** The probe reads the label, the exposure, artefact
channels and the clinical record. It never reads a candidate. That is the same class of information which
licensed E22's P4 amendment — counts and distributions computable with no result in hand — and the module
raises if a caller passes a candidate column as the label, exposure or artefact.

**The one rule that keeps it honest: the probe runs BEFORE the registration and its output is pasted into
it.** A probe run after a gate fails, used to find the setting that would have passed, is the move §2
forbids; E29's nine-cell sweep is the worked refusal. Floors are set knowing the coverage, which is the
opposite of choosing coverage knowing the floors.


---

## 2.6. Step 3.5 — a gate is not a gate until it has been seen to fail

**This project shipped two gates that could not fail, and both printed confidently.** E22 selected epochs by
`meta_epoch`, a column its adapter never emitted, so every test matched the empty string and the gate saw 0
of 0 cases. E29 checked that its pairs spanned "both directions of dose" while its own pair constructor
oriented every pair higher-dose-second, so the answer was 100.0 % by construction. That is error-catalogue
rule 40, and it is the reason this step exists as a step rather than as good intentions.

**The check is cheap and mechanical.** For each gate, build a synthetic input designed to fail it and assert
that it does; then build one designed to pass and assert that too, because **a gate that always fails is a
wall, not a gate**. Both directions, always. The fixtures are synthetic and carry no claim about any
candidate — the assertions are about control flow.

**A suite that passes on the first run is a reason for suspicion, not comfort.** Mutate the code under test
and confirm the test notices. Two examples, from the run that established this step: removing E36's
per-family capability floor made its gate stop failing on an input built to fail it (return code 1 → 0, and
the failure message vanished); disabling E37's both-present pair mask produced 281 finite autocorrelations
where the test demands zero. Both mutations were detected, which is what licensed trusting the tests.

**Where this sits relative to the other rules.** Rule 40's inverse is just as real and belongs in the same
step: E37 registered a 30 s sensitivity arm requiring 30 adjacent pairs from a 30-sample window, which
contains 29 — **a check that cannot fire**, which produced no output and would have vanished unremarked
(rule 48). And E38 shipped a gate whose floor sat *above its own estimator's reproducibility ceiling*, so it
could not have passed on any input; that was caught only because a smoke run failed and the rival
explanation was measured before anything was changed. Three failure shapes, one step: **cannot fail, cannot
fire, cannot pass.**

**When the gate is one line inside `main`**, test the statistic directly rather than the plumbing. The point
is that the line can fire, not that the file runs — `test_e37_g1f_fires_when_the_exclusion_is_outcome_related`
does this in four lines.

---

## 3. What the loop must emit, every iteration

1. A ledger row, written at step 3 — **before** the data exists, with the registering commit SHA, the
   named incumbent, and the feasibility probe's headline numbers. **Eight of the first thirteen designs
   named no incumbent at all**, which is why the field exists and why an empty one is a defect (rule 45).
2. An outcome on that row at step 5, from the vocabulary in `registry_ledger.py`: `gate_failed`, `absent`,
   `blocked`, `withdrawn`, `negative`, `positive`, `closed`. The distinctions carry meaning — `absent` is
   not `negative` (rule 31), and `withdrawn` is not `negative` either.
3. A commit and a push. **This container's disk does not survive reclamation**; the session that wrote this
   file was rebuilt from the remote twice. An artifact that has not been pushed does not exist (rule 38).

---

## 4. Running it

**Use `/loop` in dynamic (self-paced) mode**, with §1 as the prompt. Cron is the wrong tool: the steps
differ in duration by two orders of magnitude, from a three-minute registration to a two-and-a-half-hour
extraction, and a fixed interval either wastes wake-ups or truncates streams.

Pacing follows the work, not the clock: a long fallback while an extraction runs, a short one while
registering. Streams are resumable and checkpointed, so a wake-up that lands mid-extraction costs nothing.

**Budget.** The loop should stop on exhaustion of the queue *or* the token budget, and say which. Stopping
because the queue is empty is a finding — it means the next move is acquisition, not analysis, which is
exactly where all three challenges stand today.

---

## 5. The stopping conditions, stated so they cannot drift

The loop halts when **any** of these is true, and reports which:

1. **The queue is exhausted.** No registered design remains unrun and no blocker has a named, reachable
   dataset. → the next move is acquisition.
2. **The budget is spent.** → report the ledger as it stands.
3. **A registered design produced a `positive` outcome AND its successor-verification has also been
   registered and run.** *Not* on the positive alone — a single surviving result is a candidate for
   replication, not a solution. E30's +0.710 is exactly this case: it survived its placebo on one arm and
   failed its own cross-drug criterion, so the loop continues.
4. **A human stops it.**

**There is deliberately no condition of the form "a result was significant."** If one is ever added, this
document has failed and so has the loop.
