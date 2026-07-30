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
| 3 | **Register** | **no — judgement** | Predictions, gates, placebo, falsification condition. Written to a file and **committed before the data exists**. Append a row to the ledger in the same commit. |
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

## 3. What the loop must emit, every iteration

1. A ledger row, written at step 3 — **before** the data exists, with the registering commit SHA.
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
