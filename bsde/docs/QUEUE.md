# QUEUE.md — the loop's input, derived from the round-2 literature reviews

*Created 2026-07-30. Ordered by (unblocks a challenge) × (reachable now). The loop consumes this top-down;
`DISCOVERY_LOOP.md` governs how. **Termination is exhaustion of this queue, never a passing result.***

Every item names the blocker it clears, the incumbent any resulting design must beat (rule 45), and what
would make it fail. An item with no incumbent is not ready to be registered.

---

## Q1 — Acquire DOSE-I, and with it the transition Challenge C has never had

**Blocker cleared.** VitalDB captures maintenance only: the BIS strip goes on after induction and comes off
before emergence, so neither edge of the anaesthetic is labelled (verified over 250 cases — four windows in
the entire deposit sit after `aneend` at BIS ≥ 80). Every Challenge C design so far has been forced onto a
transition *inside* maintenance.

**What it is.** Zenodo 18483292, **open, CC-BY-4.0**, no DUA wait. 171 recordings, 281 procedures, 78.5 h,
2-channel fronto-temporal EEG at 125 Hz, **1,129 annotated states-of-consciousness transitions** (LOC and
ROC) and 7,328 MOAA/S depth labels.

**The catch, and it must be declared not implied.** There is **no branded depth index** — no BIS, no
Entropy, no PSI. A "conventional monitor" comparator has to be computed from the raw EEG, which makes any
"ahead of the monitor" claim a claim about *a monitor proxy we built*, not about a commercial device. State
this in the registration or the result is not what it appears to be.

**Incumbent.** The computed monitor proxy, plus the published delay figures it must be ahead of:
Pilge 2006 (PMID 16508396) measured **14–155 s**, direction-dependent, across BIS/Narcotrend/CSI;
Zanner 2021 (PMID 32040794) measured 21 ± 5 s and 26 ± 5 s for qCON with AUC 0.61–0.90 at the transition.

**Fails if:** the MOAA/S annotations are too sparse per recording to define a landmark; or the EEG is too
short around transitions to give a pre-transition window; or the monitor proxy cannot be validated against
the MOAA/S labels well enough to be a fair incumbent.

---

## Q2 — Acquire the Dryad ketamine set as a free adversarial control for Challenge A

**Blocker cleared.** Challenge A's acceptance condition is that a drug-identity probe must not out-predict
the state model. Every drug tested so far is GABAergic. **Ketamine is the documented adversarial case**:
PMID 27178861 reports a *"gamma burst"* pattern with **decreased** alpha/beta — the opposite direction from
propofol and sevoflurane — and PMID 29920532 shows propofol and dexmedetomidine moving the same bands in
**opposite directions at matched sedation depth**.

**What it is.** Dryad `10.5061/dryad.j9kd51c9q`, **CC0, fully open**, n = 10, sub-anaesthetic ketamine.

**The catch.** Sub-anaesthetic — subjects stay conscious, so there is no LOC and this cannot test
responsiveness. **It can only test the drug-identity probe**, which is precisely the half of Challenge A
that E25 passed (probe |AUC−0.5| = 0.006 against depth 0.063) on GABAergic agents alone. That pass is the
thing this dataset can break.

**Incumbent.** E25's own probe result. **Fails if:** the candidate's drug-identity probe fires on ketamine
as strongly as, or more strongly than, its depth association — which would retrospectively weaken E25's P4.

---

## Q3 — The Challenge B benchmark that already exists: Secci 2024

**Blocker cleared.** Not a dataset but a **number to beat**, which E28 currently lacks. Secci 2024
(PMID 38761713): 57 MCS patients, 30 min resting closed-eyes EEG, α-band connectivity, **79 % cross-validated
accuracy** discriminating MCS+ from MCS−.

**Two things to do.** (a) Contact the authors for data or code. (b) **Correct E28's framing regardless**:
Bruno 2011 (PMID 21674197) defines MCS+ as command-following *or* intelligible verbalization *or*
non-functional communication, so **MCS+ is not a pure command-following label** and E28's substitution
argument currently over-states the target.

**Fails if:** the data is not shareable, in which case Q3 reduces to the framing correction, which is owed
in any case.

---

## Q4 — Verify E26's suppression threshold attribution before it is quoted again

E26 declared **SR > 0** and **SR ≥ 10** as literature conventions from the perioperative-delirium work.
The review found that **neither Fritz 2016 (PMID 26418126) nor Soehle 2015 (PMID 25928189) states a numeric
SR % cutoff in its abstract** — both use cumulative suppression duration or continuous BSR. The attribution
is unverified.

**Do:** pull both full texts and either substantiate the thresholds or soften E26's wording. Also carry
Wildes 2019 (PMID 30721296, ENGAGES) into any clinical framing: EEG-guided titration to avoid suppression
**did not reduce delirium**.

**Fails if:** full text is unreachable, in which case the wording is softened and the claim withdrawn.

---

## Q5 — Decide what E30's unexplained sign reversal is

E30 found `exponent_high` at **+0.710** against propofol (Chennu, no opioid) and **−0.126** against MAC
(VitalDB), with **six of seven candidates flipping sign**. The literature review found **no primary source
documenting such a reversal** — the nearest phenomena are saturation-then-plateau (PMID 24154602, 28665814)
and transient paradoxical excitation (PMID 38412114), both different in kind.

Three explanations remain, and E31/E32 could not separate them:

1. **Dose range** — untested; both attempts were ABSENT on coverage.
2. **Montage** — 91 channels vs 2 frontal. Testable only by recomputing Chennu frontal-only, which needs
   raw Chennu, blocked by the Cambridge TLS failure (§9.17).
3. **Sampling rate** — 250 Hz vs 128 Hz, with `exponent_high`'s 20–40 Hz fit near VitalDB's 64 Hz Nyquist.
   **Testable now** by decimating a deposit we hold and recomputing.

**Do explanation 3 first — it is the only one reachable without new access**, and if the sign flips on
decimation alone, the other two become moot.

---

## Q6 — Finish E28 (running)

The eegmmidb resting table is complete (210/210). The imagery and executed-movement labels are building at
roughly a minute per subject. E28 needs 60 subjects with both. **No action beyond waiting**, then run.

---

## Not queued, and why

* **PhysioNet `eeg-gaba-anesthesia`** (2 drugs, continuous dose) — **n = 4**. Credentialed request is worth
  making, but four subjects cannot carry a cross-drug claim.
* **Bath prolonged-DoC** — access requested, not granted. Nothing to do but wait.
* **A finer-grid Challenge C retest on VitalDB** — E27 established that resolution cannot preserve both the
  question and the base rate at this suppression rate (rule 44). DOSE-I supersedes it.
