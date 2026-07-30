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


---

## Q1 RESULT — DOSE-I acquired and probed. It clears blockers on BOTH A and C.

*Loop iteration 1, 2026-07-30. Metadata and static tables read via the Zenodo API and `zipfile`; **no signal
data downloaded**, and the 724 MB `data.zip` remains untouched. This is step 2.5 doing its job: the design
is assessed before the archive is fetched.*

**Feasibility probe, on 171 recordings, reading no EEG at all:**

| check | result |
|---|---|
| SOC transitions | **1,129 total**, median 6 per recording, **all 171** have ≥ 2 |
| MOAA/S assessments | **7,328 total**, median 39 per recording |
| distinct MOAA/S levels per recording | **median 5**; **171 of 171** span ≥ 3 |
| EEG ch1 completeness | median **99.5 %**; all 171 above 80 % |
| propofol dose (`PROP_sum`) | 40–540 mg, **zero-fraction 0.0 %** |
| **usable for a transition design** | **171 of 171** |

**Compare the exposure to VitalDB's, which is the deposit four Challenge A designs ran on:** MAC there was
**53 % exactly zero** with a low-tercile median of 0.00, and that defect went unnoticed through four
correlational designs (rule 43). DOSE-I's dose column has **no off-state at all**.

**THE FINDING THAT MATTERS MOST: THIS DEPOSIT HAS NO CO-TITRATED OPIOID.** `drugs_opioids`,
`drugs_benzodiazepines` and the rest sit in the **static/baseline** table alongside comorbidities — they are
chronic home medications, not procedural drugs. **The only procedural drug event recorded is `PROP_sum`.**
156 of 171 subjects are not on chronic opioids either, and **not one** is on benzodiazepines.

E29 closed with a named acquisition target: *"a deposit with a graded hypnotic dose axis and no co-titrated
opioid — a volunteer study, not a surgical one."* DOSE-I is a procedural-sedation deposit that satisfies it,
at **n = 171 against Chennu's 20**, and it is open CC-BY-4.0 with no credentialing wait.

**AND MOAA/S IS NOT A DOSE PROXY — IT IS RESPONSIVENESS, MEASURED.** The Modified Observer's Assessment of
Alertness/Sedation is a graded *behavioural* scale scored by a clinician at the bedside. Challenge A asks
for a representation *"predicting loss and recovery of responsiveness"*. Every previous attempt in this
project substituted something for responsiveness — a charted time (E21), a depth index that turned out to be
muscle (E22), administered dose (E25, E29, E30). **DOSE-I supplies the actual construct, repeatedly, within
subject, in 171 people.**

**What must still be checked before registering** — and it is not optional:

1. **Is the propofol time course available, or only the cumulative total?** `PROP_sum` is per-recording.
   A within-subject dose-response needs administration events over time; the readme's "Drug-related Events"
   section implies they exist in `data.zip` but this has not been verified.
2. **Is MOAA/S timestamped against the EEG clock?** A graded label is useless if it cannot be aligned to a
   window. 7,328 assessments across 171 recordings implies timestamps, but implication is not verification.
3. **What artefact channel exists?** The EMG confound that killed E22 was only detectable because VitalDB
   ships `BIS/EMG`. DOSE-I lists `Intellivue/EEG_1` and `EEG_2` and a `pEEG` feature set — **if there is no
   muscle channel, the E22 check cannot be run here and that limitation must be declared, not assumed away.**
4. **No branded depth index.** Any "ahead of the monitor" claim is about a proxy we compute, as Q1 already
   states. That is a real weakening and belongs in the registration.

**Queue consequence:** Q1 is not finished — it is now three sub-items (verify the drug time course, verify
MOAA/S alignment, identify an artefact channel), and only then a registration. **No experiment is registered
on DOSE-I yet**, and the next loop iteration does those three checks rather than writing predictions.


### Q1 VERIFICATIONS — all four answered from `pEEG.zip` (28 MB). `data.zip` still untouched.

Each recording ships a `*_pEEG.csv`: **1-second resolution**, 171 recordings, median 26 min, 49 columns.

| open question | answer |
|---|---|
| propofol time course, or only a cumulative total? | **Per-second `Propofol` column, non-empty in 40,800 of 40,800 rows scanned.** |
| is MOAA/S aligned to the EEG clock? | **Yes — per-second, all five levels present** (1: 24,992 · 5: 5,785 · 3: 4,039 · 4: 3,760 · 2: 2,224) |
| is there an artefact channel? | **No dedicated EMG.** `abs_gamma`/`rel_gamma` are the EMG-sensitive bands and are a proxy, not a channel. **The check that killed E22 cannot be run here in its strong form, and that is a declared limitation.** |
| is there a monitor to be ahead of? | **Better than assumed.** The deposit ships **SEF95, MF (median frequency), WSMF variants and permutation entropy (PE31/PE32/PE61)**, non-empty in 86 % of rows. |

**The "no branded monitor" caveat is smaller than Q1 claimed and is corrected here.** SEF95 and median
frequency are the published algorithms commercial depth monitors are built on, and permutation entropy is an
established depth index in its own right. The incumbent is therefore **a published depth measure, not a
proxy invented for this project** — a materially stronger comparator than Q1 anticipated. It is still not a
branded device output, and any claim must say "ahead of SEF95/PE", never "ahead of BIS".

**A detail that makes this deposit unusually well-suited to the question.** Ostertag 2025 (PMID 38412114)
found that **SEF95 and spectral entropy move the WRONG way at loss of responsiveness while permutation
entropy tracks it correctly.** DOSE-I ships both families pre-computed. The incumbent comparison therefore
has a published expectation attached to it before anything is run.

`SOC` is binary and populated: 25,540 unconscious against 15,260 conscious in the 25 recordings scanned — a
base rate around 37 %, comfortably inside any sane band, unlike E27's 4.0 %.

**Q1 is CLOSED as an acquisition item.** What follows is a registration, not more verification.
