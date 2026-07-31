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


---

## Q7 — Chennu 2014's DoC cohort: the only public dataset found with a real command-following label

**Verified by the orchestrator, not taken from the review.** `efetch` on PMC4199497 returns Table 1 with the
column headers, verbatim:

    Patient | Post-ictal Interval | Gender | Age at Assessment | Etiology | Diagnosis | CRS-R |
    **Command Following (CRS-R)** | **Command Following (fMRI)**

**Two independent command-following labels per patient**, one behavioural and one imaging. And the table
contains the phenomenon Challenge B exists for: **P3 is a VS patient scoring `No` on CRS-R and `Yes` on
fMRI — a cognitive motor dissociation case, in the published table.**

* Chennu S et al., 2014, *PLoS Comput Biol*, **PMID 25329398**, open access (CC BY).
* **32 DoC patients**, 10 minutes of **128-channel resting-state EEG**, 250 Hz, eyes open. Genuinely
  task-free — which is exactly what Challenge B asks about.
* **This is a different cohort from the Chennu propofol-sedation data already in this repo.** Same group,
  different study. `ingestion/chennu.py` does not read it.

**Access route:** raw EEG is not open. From the paper's own data-availability statement: *"data are
available by request to either the study authors or the Wolfson Brain Imaging Centre's data protection
officer (enquiries@wbic.cam.ac.uk) for researchers who can meet the requisite ethical criteria... subject to
case-by-case review."* A defined committee route, not a de novo ethics application.

**Why this outranks everything else for Challenge B.** The review confirmed, via each repository's own API,
that OpenNeuro and Dryad hold **no** DoC EEG dataset at all, and that CRS-R subscale data is essentially
absent from public repositories. The 237-patient Della Bella cohort (**PMID 40796934**, verified) publishes
only CRS-R *totals* and requires an author request for signal. **Chennu's is the only command-following
label located anywhere.**

**Action: request it.** Until then Challenge B has no ground truth and E28's healthy-BCI substitution
remains an unvalidated analogy — the review confirmed **no published work tests transfer from healthy or
sedated populations to DoC**, in either direction.

---

## Q8 — Krause/Banks: dexmedetomidine, propofol AND natural sleep in one cohort

**The second drug Challenge A has been blocked on, and it instruments the sleep-control idea in the same
deposit.** Verified against the Zenodo API and PubMed directly.

* Krause BM et al., 2026, *Br J Anaesth*, **PMID 41203472**: *"Dexmedetomidine produces more sleep-like
  brain activity compared with propofol in human participants."*
* Zenodo **10.5281/zenodo.15497531** — `DexProSleepPackage.zip`, **2.1 GB, open**. Code BSD-3-Clause,
  **data CC-BY-SA 4.0**.
* **10 dexmedetomidine · 19 propofol · 24 natural overnight sleep**, intracranial EEG, 34 epilepsy-surgery
  patients. Responsiveness by **OAA/S**, block-level three-class (wake / sedated / unresponsive). Sleep
  staged separately at 30 s.
* **Dexmedetomidine is an alpha-2 agonist, not GABAergic** — the pharmacologically furthest reachable agent
  from propofol, and PMID 25187999 / 29920532 document it producing opposite-signed EEG effects at matched
  sedation depth. That is exactly the adversarial case Challenge A's drug-identity probe needs.

**Three limitations that are not small and must be carried into any registration:**

1. **Intracranial, not scalp.** DOSE-I and Chennu are scalp. A cross-drug test spanning them is also
   cross-modality, and that confound cannot be absorbed silently into "drug generalisation".
2. **Block-level OAA/S**, not DOSE-I's per-second MOAA/S. Either bin DOSE-I down to match or state the
   resolution mismatch as a limitation — do not paper over it.
3. **Epilepsy-surgery population** with patient-specific electrode coverage.
4. **CC-BY-SA on the data** — ShareAlike, which is the propagation risk Invention Notebook entry 12 tracks.
   Raw continuous iEEG additionally needs a University of Iowa DUA; only derived features are open now.

**Two things the review flagged that I am carrying as corrections rather than support:**

* **Lendner 2020 (PMID 32720644) may be cited as precedent for validating a marker across sleep and
  anaesthesia — NOT for "sleep proves the absence of drug-identity information".** That is a stronger and
  different claim than the paper makes, and the distinction must be stated wherever the sleep-control
  argument is used.
* **Sleep stage is not a graded elicited responsiveness score.** Nobody tests command-following during
  sleep, because testing would end it. Sleep is defensible as an arousal-level analogue and is a stretch if
  the acceptance criterion needs behavioural responsiveness.
* **No published precedent exists for a drug-identity adversarial probe in this domain**, under any phrasing
  tried. If this programme gates on one, that is original methodology requiring its own validation, not a
  field-standard practice to cite.


---

## Q8 RESULT — Krause package downloaded and probed. It gives Challenge A its acceptance-condition test.

*2.1 GB pulled from Zenodo 15497531. The 2.3 GB `AllMatData` is NOT needed: `allData.csv` inside the package
carries per-patient, per-state derived features and is 1.9 MB. Extracted to
`results/krause_dexprosleep_allData.csv`.*

**Structure, verified by parsing rather than from the paper:** 12,313 rows, **34 patients**, 27 columns.

| arm | labels | rows |
|---|---|---|
| propofol | `WA` 119 · `S` 77 · `U` 129 | wake / sedated / unresponsive |
| **dexmedetomidine** | `WA_dex` 49 · `S_dex` 111 · `U_dex` 66 | same three-level OAA/S ladder |
| natural sleep | `WS` 4,456 · `N1` 713 · `N2` 4,519 · `N3` 645 · `R` 1,429 | staged PSG |

**Patients by arm combination:** 13 propofol+sleep · 6 propofol only · 6 dex+sleep · 5 sleep only · 4 dex
only. So **19 propofol, 10 dexmedetomidine, 24 sleep**, matching the paper.

**Features shipped:** `EffDim` (effective dimensionality), `NmlzCmplx` (normalised complexity),
`allEnvCorr`, `AvgDelta`/`AvgAlpha`/`AvgGamma`, regional deltas, `frontalAlpha`, five wPLI variants, and
`frontBias`.

**WHY THIS IS THE TEST CHALLENGE A HAS BEEN MISSING.** Its acceptance condition is that a drug-identity
probe must not out-predict the state model. Every previous attempt could only probe GABAergic agents against
each other — E25's probe compared sevoflurane against desflurane, two volatiles. **Here the comparison is
propofol against dexmedetomidine at MATCHED unresponsiveness** (`U` against `U_dex`, 129 rows / 19 patients
against 66 / 10), and dexmedetomidine is an alpha-2 agonist with documented opposite-signed EEG effects at
matched sedation depth (PMID 25187999, 29920532). **This is the adversarial case, not another instance of
the same case.**

**And sleep supplies a no-drug arm in the same patients** — 13 propofol and 6 dex patients also have staged
sleep, so a within-patient comparison of drug-unresponsiveness against N2 is available without crossing
cohorts.

**Four limitations carried from Q8 and now sharpened by the parse:**

1. **Block-level, not per-second.** These are ~6–7 min blocks. DOSE-I's MOAA/S is per-second. Any joint
   analysis bins DOSE-I down or states the mismatch; it does not average over it silently.
2. **Small drug arms.** 10 dexmedetomidine patients. A probe on 10 versus 19 patients is a real test but a
   thin one, and the interval will say so.
3. **Intracranial and epilepsy-surgery.** Not scalp, patient-specific coverage, abnormal networks possible.
   A cross-deposit claim against DOSE-I or Chennu is also cross-modality.
4. **CC-BY-SA on the data** — ShareAlike, the propagation risk Invention Notebook entry 12 tracks. Recorded
   in the licence registry before anything derived from it is published.

**Next: register the drug-identity probe.** Not the state model — the probe. It is the half of Challenge A
that E25 passed on GABAergic agents alone, and it is the half this deposit can break.

---

## Q9 — the successor E36 earns, and the one it cannot run here

**Status: OPEN. Blocker named and it is not solvable inside any deposit currently held.**

E36 established two things on the Krause deposit and refuted one alternative explanation:

* the phase/amplitude split in drug legibility is the unique maximum of all 495 exhaustive 4/8 splits
  (p = 0.002), so it is not a line drawn through noise after the fact;
* the capability gap between the families is **-0.017 [-0.107, +0.081]** — centred on zero — so "phase
  measures leak less because they measure less" is excluded to within ±0.10 legibility units;
* and, **post hoc and therefore only a hypothesis**, the mundane methodological explanation fails: within a
  single drug arm phase measures are *more* legible of electrode type than amplitude measures (0.243 vs
  0.202 propofol, 0.344 vs 0.288 dex), so they are not a generically artefact-robust family.

**What Q9 must do.** Pre-register the within-arm nuisance comparison that E36 could only run post hoc, and
run the whole thing on a cohort where **the arms share patients**. E36's structural limit is that its two
arms share 0 patients of 29 and both nuisance channels are patient-constant, so drug arm, electrode type and
data quality are nested inside patient identity and no method separates them there.

**Blocker.** No public deposit located pairs raw EEG with two mechanistically distinct anaesthetics in the
same patients. The searches behind that statement are Q8's, across PubMed, OpenNeuro, Dryad, Zenodo, OSF,
Figshare and PhysioNet. Until one exists, the E35/E36 observation stays unclaimed — which is its recorded
status, not a stalled task.

**What is worth doing in the meantime, in order.**

1. **A crossover or within-patient two-agent design is the whole ask.** Worth one targeted search of trial
   registries rather than data repositories: a registered crossover study with an EEG endpoint may have
   deposited data under a title no repository search would surface.
2. **Recompute the features rather than inheriting them.** Every number in E35 and E36 comes from the
   depositors' feature pipeline. `verifier/` has an independent wPLI (`wpli_alpha`, definition fingerprint
   `8ddebb740c943a76`) already used on four scalp cohorts. If the Krause raw traces are obtainable, the
   family split should be re-measured with our own implementation before it is taken anywhere — rule 23,
   self-written code and self-written tests share blind spots, and here we have neither: we have someone
   else's code and no tests at all.
3. **Nothing about this belongs in a scalp claim yet.** Intracranial coverage in epilepsy-surgery patients
   is the scope limit, and the Chennu and ds004541 cohorts cannot substitute because neither has a second
   agent.

---

## Q10 — Challenge C's consolidated position, and the successor that was designed and then abandoned before it ran

**Status: the negative is now the result. No sixth design is queued, and that is a conclusion rather than a
stall.**

Five Challenge C designs, three reportable verdicts, and they converge on one shape:

| design | instrument | against chance | against the incumbent |
|---|---|---|---|
| E26 | spectral level, 300 s grid | — | negative, every gate passed |
| E33 | spectral level, run-up sampling | gate-failed, position-AUC 1.000 | — |
| E27 | spectral level, 60 s grid | absent (base rate 4.0 % at SR ≥ 10) | — |
| E34 | permutation entropy per window | 0.623 [0.587, 0.659] | **+0.0178 [-0.0226, +0.0474]** |
| E37 | lag-1 autocorrelation of the incumbent's own trajectory | **0.582 [0.524, 0.635]**, adj p 0.0010 | **+0.0007 [-0.0539, +0.0295]** |

Three different instruments — a spectral level, an ordinal-pattern complexity, and a second-order dynamical
statistic derived from published phase-transition theory — and every one of them **clears chance and fails
to clear SEF95's own level.** E37 is the sharpest case: its primary was signed in advance by Steyn-Ross
(PMID 14525001), it fired in the predicted direction with an adjusted p of 0.0010, and it added nothing.

### The successor that was designed and then killed by a five-minute feasibility check

E37's write-up named the obvious next question: is SEF95's dominance a property of the brain, or of the
label? `SOC` is a charted flag, and a charted flag has its own latency — if it were derived from or charted
alongside the depth monitor, the incumbent would be partly predicting its own shadow. DOSE-I ships
**`MOAAS` per second in all 171 files**, so the design was to re-run the incumbent against a MOAA/S-derived
landmark and compare.

**It cannot be run, and the check that killed it is error-catalogue rule 19 — before two measures can
corroborate each other, ask whether one row can satisfy both definitions.** `SOC == 1` and `MOAAS > 1` agree
on **95.6 % of samples on average and 98.0 % at the median**. They are not two labels; they are one label
recorded twice. No contrast between them can separate label provenance from brain signal.

**The check pays for itself in the other direction, and this is the part worth keeping.** Because `SOC`
tracks a *behavioural* scale almost exactly, the incumbent is **not** winning by predicting a
monitor-derived label. The circularity that would have deflated E26, E34 and E37 is ruled out, and the
Challenge C negative is therefore stronger than it looked, not weaker.

### What would actually move Challenge C, in order

1. **The spatial half of the theory, which nothing here has tested.** Steyn-Ross's own primary prediction is
   that EEG correlation *length* grows on approach to induction. DOSE-I is single-site, so E37 tested the
   temporal half only and said so. `ds004541` has raw multichannel recordings with LOC and ROC landmarks —
   and **8 subjects**, which is why it is listed as a direction rather than a queued design.
2. **Ask whether the ceiling is the transition's own sharpness.** E37's lead-time curve decays from 0.561 at
   30 s to 0.497 by 180 s: whatever information exists arrives just before the loss, which is exactly where
   the incumbent is also strongest. A design that could separate "no information earlier" from "no
   information the incumbent lacks" would be worth more than a sixth feature.
3. **Nothing further on DOSE-I with a new feature.** Three instruments have now failed in the same place.
   A fourth feature is the least informative thing this queue could spend a run on.

---

## Q11 — ds005620's awakening reports: the dissociation label exists, and it is not in the deposit

**Status: OPEN, and the cheapest unblocked action in the queue. A data request, not an experiment.**

`DATASET_REGISTRY.csv` already flagged ds005620 as a "CRITICAL dissociation test: unresponsive WITH reported
experience", with the events column marked `REQUIRES VERIFICATION`. It has now been verified, by listing the
deposit from S3 rather than by any fetch-tool summary (rules 25 and 39), and the answer is **the reports are
absent**.

What the deposit actually contains, from `README.txt` and a full prefix listing of one subject (78 keys):

* the design is a **repeated-awakening study during propofol sedation**, up to 3 awakenings per subject;
* **`task-sed2` is "One-minute resting EEG recorded just before an awakening"** — so every awakening has a
  matched, clean, pre-awakening minute of resting EEG, which is precisely the window a dissociation test
  needs, and it is already downloaded (`ds005620_features.csv`, 202 recordings, 21 subjects);
* `participants.tsv` gives an `awakenings` **count** per subject (0–3) and nothing about what was reported;
* `events.tsv` for a rest run contains a single `New Segment` row. There is no `_beh` file, no phenotype
  directory, and the deposit's top level holds six files in total.

**So the EEG for the dissociation is public and the label is not.** That is a different blocker from
Challenge B's — not "no such dataset exists" but "this dataset's outcome column was not uploaded".

**Why it is worth asking for.** A subject who is behaviourally unresponsive under propofol and afterwards
reports an experience is the anaesthesia analogue of covert consciousness, and it separates *arousal* from
*cognitive processing* in the same person, which is Brief 01's actual question. It is closer to the flagship
than E28's healthy-BCI substitution is, because the dissociation is real rather than analogical. It also
bears on verifier layer 6.

**Why it is cheap.** The deposit is CC0/CC-BY (see the licence note — it declares both), from a group that
publishes openly, and the README lists author contacts directly: Imad J. Bajwa (`imadjb@uio.no`) and
Bjørn E. Juel (`Bjorneju@gmail.com`). The ask is one table: per subject, per awakening, whether an
experience was reported and ideally its content class. No raw data transfer, no patient identifiers, no
ethics obstacle of the kind Chennu's DoC cohort raises — these are healthy volunteers.

**Draft ask, to be sent by the investigator:** request the per-awakening report labels corresponding to the
`task-sed2` / `task-sed run-1..3` recordings already public on OpenNeuro; state that the intended use is
methodological (testing whether resting EEG measures separate unresponsiveness-with-experience from
unresponsiveness-without), offer co-authorship or acknowledgement as they prefer, and offer to share the
analysis code and any derived table back.

**What this does NOT unblock.** ds005620 is propofol only, so it does nothing for Q9's two-agent problem;
and it is healthy volunteers, so nothing from it transfers to a DoC claim without saying so.
