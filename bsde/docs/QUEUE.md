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
2. **~~Recompute the features rather than inheriting them.~~ CLOSED 2026-07-31 — NOT ACHIEVABLE ON THIS
   DEPOSIT.** The intent was a rule-23 check: every number in E35 and E36 comes from the depositors'
   feature pipeline, and `verifier/` has an independent wPLI (`wpli_alpha`, fingerprint `8ddebb740c943a76`)
   that could have re-measured the family split. **The Krause deposit ships no raw traces.** Its 215
   entries were enumerated without downloading the 2.1 GB package, by an HTTP range request for the ZIP
   central directory: no EDF, no iEEG, no continuous recordings — one 2.3 GB `.mat` of derived
   per-electrode data, figures, and MATLAB/R code. So the features cannot be recomputed from signals here
   by anyone, and the check is unavailable rather than pending. It would become available only with a data
   request to Krause/Banks for the traces, which is a separate ask from the Turku one below and a larger
   one. **Recorded as a closed item rather than deleted, because "we never checked" and "we checked and it
   cannot be done" are different states.**
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

---

## Q12 — Challenge B: what E28's gate failure actually established, and why the successor asks about the label

**Status: E38 registered and running. E28 stands as ABSENT and its floor is not being moved.**

E28 was Challenge B's healthy-BCI substitution — motor imagery is command-following that produces no
movement, so it has the right *form* even though a healthy subject who cannot drive a BCI is not
unconscious. Its machinery gate refused before any resting feature was read:

* **17 of 104 subjects (16.3 %)** beat their own permutation null at p < 0.05, against a registered floor of
  20 %. Median imagery AUC 0.531 against a median per-subject null of 0.461.
* The label **varies** (IQR 0.212, floor 0.10) and **coverage passed** (104 subjects, floor 60).

**The machinery is not broken, and the placebo arm is what shows it.** Executed movement — real fist
movement, necessarily easier to decode than imagined — scores a median AUC of 0.545 with **24.0 %** beating
their own null. The ordering executed > imagery is right in both statistics, and 17 of 104 past p < 0.05
where 5 are expected by chance is real signal. **So the label carries signal at the level of the cohort and
almost none at the level of the subject**, and it is the second that Challenge B's substitution needs.

**The cause is arithmetic, not biology.** `eegmmidb`'s imagery left/right protocol is runs R04, R08 and R12
— **45 trials per subject, about 22 per class, and that is the entire deposit**. A per-subject permutation
test at that size reaches p < 0.05 only for a large true effect.

**The gate asked for the wrong quantity, and saying so changes nothing.** Its 20 % floor was a lenient
reading of the BCI-illiteracy literature's 70-85 %, which is a **prevalence** measured over hundreds of
trials; the gate applied it to a **detection rate** at n = 45. That is rule 30 exactly — pre-registration
stops a bar moving afterwards, it does not stop it being set badly, and the paperwork looks correct either
way. Lowering it now would be indistinguishable from moving it, whatever the justification, so E28 stands.

### E38, the successor, and why it is worth more than E28's verdict would have been

The instrument changes from a significance rate to **reliability**: split each subject's trials in half,
decode each half independently, and correlate the two per-subject estimates across subjects. Spearman-Brown
gives the reliability of the full-length label, and its square root is the **attenuation ceiling** — the
largest correlation any resting-state feature could have with this label, however good the feature is.

That number bounds every future experiment on this deposit rather than settling one candidate, and it can
**kill the healthy-BCI substitution honestly**, which is what Challenge B most needs and what no
candidate-scoring experiment can deliver. E38 reads no resting-state candidate at all.

Its P2 arm is registered rather than added later because it discriminates two diagnoses with different
consequences: **executed reliable and imagery not** means the deposit supports per-subject labels and
imagery specifically is too weak here; **neither reliable** means 45 trials is too few for any per-subject
label in this deposit, and the same verdict follows for any task in it.

### Challenge B's standing position, unchanged by any of this

No public deposit pairs task-free EEG with a per-patient command-following label. The WBIC request for the
Chennu 2014 DoC cohort is out. Q11's ds005620 request — the awakening reports whose EEG is public and whose
outcome column was never uploaded — is drafted and not sent, and is the cheaper of the two asks. E28's
substitution was always an analogy under test and its scope limit stands whatever E38 returns: **no sentence
from either file may be written as a claim about disorders of consciousness.**

---

## Q9 addendum (2026-07-31) — the cohort Q9 says does not exist has been published on

Q9 states that no public deposit pairs raw EEG with two mechanistically distinct anaesthetics in patients
who share arms. That remains true of *deposits*. It is not true of *cohorts*: **Kallionpää et al.,
Br J Anaesth 2020 (PMID 32773216, NCT01889004)** recorded 64-channel EEG in 47 healthy volunteers on
dexmedetomidine (n = 23) or propofol (n = 24), with **within-subject loss and return of responsiveness at
constant dosing** — the design that separates state from drug concentration, and precisely the thing E36
identified as structurally impossible in the Krause deposit.

**So the Turku/Scheinin group is a data-request target**, on the same footing as WBIC (Q10 of the Challenge
B thread) and ds005620 (Q11), and a better one than either for Challenge A specifically. Whether the data
can be obtained is unknown and untested; nothing here should be read as saying it is available.

Two things this does not change. The arms in that study are still **between-subject** for drug (each
volunteer received one agent), so it does not by itself supply a within-patient two-agent contrast — what it
supplies is a within-subject *state* contrast at fixed concentration, which is the more important half.
And E35/E36's own claim status is unchanged: still unclaimed, now with external corroboration rather than
none.

---

## Q13 — E39 and the sizing problem it exposed

**Status: E39 ran and returned NO EVIDENCE. The deflationary explanation for E35/E36 is live and untested at
adequate power, and this entry records what adequate power would take.**

E36's defence of the measure-family split — that phase measures are not generically artefact-robust — was
post hoc, unregistered, and ran on the same intracranial rows as the finding it defended. E39 pre-registered
it on two independent scalp cohorts with **our own** wPLI implementation, using EMG as the artefact channel
and registering the direction that would **weaken** E35/E36. Result:

    ds004541   Contrast +0.0113 [-0.1750, +0.1966]        (8 subjects, 124 rows)
    chennu     Contrast +0.0417 [-0.1935, +0.2674]        (20 subjects, 80 rows)

Both gates passed in both cohorts, so the null is about power rather than machinery. **Both point estimates
lean toward the deflationary explanation and that is not evidence** — two estimates of +0.011 and +0.042
with intervals near ±0.2 agreeing in sign are two coin flips landing the same way.

The per-feature table is worth more than the primary: **our wPLI sits mid-pack on EMG legibility in both
cohorts** (0.045 and 0.100, against spreads of 0.006-0.148 and 0.050-0.175 across six amplitude and
complexity measures). The *strong* version of the deflationary story — wPLI barely responds to artefact — is
not what these tables look like. That is a weaker claim than a significant contrast, and it is the one the
data supports.

### What a properly-powered attempt needs, and what it would cost

Three deficits, in order of how much each cost:

1. **More than one phase measure.** `wpli_alpha` is the only phase feature in the registry, so E39's
   statistic was "wPLI against the rest" rather than a family mean, and had no way to average down noise on
   the side that mattered. E36's Delta averaged four. **Adding phase measures — dPLI, imaginary coherence,
   a front/back wPLI contrast — is a registry change plus a re-extraction, not a new deposit.**
2. **More subjects with the artefact channel.** `emg_index` exists only in `ds004541` and `chennu`, because
   only those two were processed with the fuller feature set. `ds005620` (21 subjects) and `ds007554` (15
   subjects) have `wpli_alpha` and **no EMG columns**. Re-extracting those two with the full feature set
   would roughly triple the subject count to ~64 — one S3 pass over ~445 recordings, hours, and no new
   access.
3. **Many windows per subject.** `chennu` ships four rows per subject, which makes its within-subject EMG
   split 2-versus-2 and its state contrast 1-versus-1; it was never going to contribute a usable interval.
   `ds004541` at ~15 rows per subject is the shape to aim for.

**Do the arithmetic before the run, not after.** E39's intervals are the input: a design that cannot detect
a Contrast of ~0.05 is not worth executing, and these intervals say what n would be needed to see one.
Error-catalogue rule 41 — run the feasibility probe before registering — extends naturally to power, and
E39 is the entry that earns that extension.

**Not queued as an immediate action.** The two re-extractions compete for the same S3 bandwidth as the
eegmmidb trial cache, and Challenge A's larger blocker is the one Q9 records — every reachable deposit has
its two agents in disjoint patients. A better-powered artefact test sharpens a defence of a finding that is
already externally corroborated by Kallionpää 2020 and Akeju 2014; it does not unblock the challenge.

---

## Q10 item 2 — CLOSED 2026-07-31. The information-horizon question cannot be asked on DOSE-I at all.

Q10 named this as the one thing worth more than a sixth feature: *"A design that could separate 'no
information earlier' from 'no information the incumbent lacks'."* E40 built it — disjoint bands instead of
E37's nested horizons, the position check promoted from report to gate, the raw out-of-fold AUC instead of a
folded one. **All eight bands were refused by their own gates**, seven on position at 0.026-0.060 against a
0.20 ceiling.

**A feasibility probe run before registering any successor shows no successor can be built.** Position-matched
controls do not exist at the lead times that matter:

| band | band windows with a within-record control within 0.10 position | recordings contributing |
|---|---|---|
| [0, 30) s | 1,045 of 14,220 | 38 |
| [60, 120) s | 485 of 11,450 | 15 |
| [180, 240) s | 60 of 3,369 | 1 |
| [300, 420) s | **0 of 2,131** | **0** |

**The reason is structural.** In DOSE-I, "far from a loss" means "after the last loss", because procedural
sedation cases end awake — the control class is 26,489 no-loss-after windows at median position 0.90 against
819 genuinely-far windows, while band windows sit at 0.26-0.35. There is no population of early-in-record
windows far from any loss, because every case's early portion leads into an induction. **Closed as
checked-and-impossible, like Q9 item 2, rather than left pending.**

**And a second, independent flaw that this project's own verdict code was hiding.** E40's band test was
one-sided (`lo > 0.5`), so its placebo printed "at chance" in every band while SEF95 scored **0.237 [0.115,
0.418]** under a *fake* landmark — an interval lying entirely *below* chance, which is discriminable, not
null. Two-sided, the placebo is discriminable in **5 of 7** gated bands and the curve is not flat. Rule 37,
third occurrence. Had the position gate passed, E40 would have reported a horizon while printing "placebo
curve flat at chance: True" beneath it.

**What would answer the question, if anything.** A deposit where inductions occur at varied positions within
a recording, or where control periods are interleaved with inductions rather than trailing them — I-CARE's
serial per-patient recordings across days are the nearest shape held, and they carry no induction at all.
**This is a data-shape requirement, not an analysis problem, and it should be checked against any future
deposit before that deposit is acquired for Challenge C.**

---

## Q14 — Stieger 2021 is the deposit Challenge B needs, and E38's ceiling is what identifies it

**Status: OPEN, feasibility-probed, and the highest-value unblocked item in the queue.**

E41 left Challenge B with an arithmetic problem, not a scientific one: the primary was an underpowered null
(|rho| = 0.076 against a minimum detectable 0.272), and E38's reliability interval permits a true value low
enough that **n = 239** would be needed. eegmmidb has 109 subjects and cannot supply more.

**The instinct — find a deposit with more subjects — is wrong, and E38 is what shows it.** Reliability, not
n, is the binding constraint: the ceiling `sqrt(r_sb) = 0.5402` attenuates every association before the
sample size is even considered. **More trials per subject buys more than more subjects.**

### The deposit

Stieger JR et al., "Continuous sensorimotor rhythm based brain computer interface learning in a large
population," *Sci Data* 2021. **PMID 33795705**, DOI 10.1038/s41597-021-00883-1. Data: figshare
**10.6084/m9.figshare.13123148**, **CC BY 4.0**, 599 files, **376.9 GB** — all verified through the figshare
REST API with `curl`, never a fetch-tool summary (rules 25, 39).

**62 healthy adults, up to 11 sessions each, 598 recording sessions, over 250,000 trials, 600+ hours.**

One session file was downloaded and read directly. Its structure, verified rather than assumed:

* `BCI.data` — **450 trials**, each **62 channels x ~8.4 s at 1000 Hz**
* `BCI.TrialData` — per trial: `tasknumber`, `runnumber`, `trialnumber`, `targetnumber`, `triallength`,
  `targethitnumber`, `resultind`, **`result`**, `forcedresult`, **`artifact`**
* S1 session 1: 214 hits / 122 misses, **accuracy 0.637**; `forcedresult` 0.631; **0 artifact-flagged trials**
* `BCI.metadata` — **`age`, `gender`, `handedness`, `meditationpractice`, `athlete`, `instrument`, `date`,
  `day`**

### It fixes three of E28/E41's weaknesses at once

1. **Label precision.** 450 trials per session against eegmmidb's **45 in total**. Reliability should
   approach 1, lifting the ceiling from 0.54 toward 1 and removing the attenuation that made E41
   underpowered. At n = 62, an incumbent-strength predictor (Blankertz r = 0.53) is detectable at 2.3-4.5
   SE across reliabilities from 0.3 to 1.0, against a minimum detectable r of 0.349. **Fewer subjects,
   decisively better power** — which is the whole point E38 established.
2. **Demographics.** E28 names its largest weakness plainly: *"`eegmmidb` ships no demographics at all, so
   none can be adjusted for."* Age, sex and handedness are in every session's metadata here.
3. **Longitudinal structure.** Up to 11 sessions per subject supports genuine **test-retest** reliability
   rather than the split-half estimate E38 had to use, and lets learning be separated from ability.

### What has to be built, and the order

1. **A Stieger adapter.** MATLAB v7 `.mat`, `scipy.io.loadmat` reads it (not HDF5 — h5py fails on the file
   signature). Process-and-discard: one 600 MB file at a time, so peak disk is one file against ~21 GB free.
2. **E42 — measure the reliability FIRST, exactly as E38 did for eegmmidb**, and with test-retest across
   sessions rather than split-half. **Do not run the correlation until the ceiling is known.** That
   sequencing is the single most useful thing E38 established and it should now be standard.
3. **E43 — the correlation**, with the measured ceiling in its header (rule 45 and E38's verdict), the
   incumbent named, and demographics available as covariates for the first time in this challenge.

**The resting-state question to settle before registering E42:** Blankertz's predictor is computed from a
*"relax with eyes open"* recording, and Stieger's sessions are task trials throughout. Whether a usable
task-free segment exists — a pre-cue baseline, an inter-trial interval, or a separate baseline run — is a
feasibility check on `BCI.time` and `TrialData`, and it must be answered **before** E42 is registered, not
after it fails. Rule 41.

---

## Q15 — the deposit shape E40 asked for may already be held, and it is ds005620

E40 closed the information-horizon question on DOSE-I and named what would reopen it: *"a deposit where
inductions occur at varied positions within a recording, or where control periods are interleaved with
inductions rather than trailing them."* DOSE-I fails because procedural sedation cases end awake, so "far
from a loss" and "after the last loss" are the same windows.

**ds005620 has that shape by design.** It is a repeated-awakening propofol study: each subject is sedated,
woken, re-sedated, up to three times (`task-sed run-1..3`, with `task-sed2` documented in the deposit's own
README as *"One-minute resting EEG recorded just before an awakening"*). Transitions therefore occur at
several positions inside a session, with responsive and unresponsive periods interleaved rather than one
trailing the other — which is exactly the control-class structure E40's position gate rejected DOSE-I for.

**Three things to check before this becomes a registration, and the order matters (rule 41).**

1. **The transitions are AWAKENINGS, not inductions.** That is return of responsiveness, not loss of it, so
   this is E24's question ("EEG ahead of the monitor at emergence", currently `blocked`) rather than E40's.
   Whether the information-horizon framing transfers across the two directions is an assumption and must be
   stated, not assumed — hysteresis between induction and emergence is the central claim of the
   Steyn-Ross model E37 tested, so the two directions are explicitly *not* interchangeable there.
2. **Are the transition times actually recoverable?** `task-sed2` ends at an awakening by construction, so
   the landmark is the run boundary rather than an annotation. `events.tsv` for a rest run holds a single
   `New Segment` row (verified in Q11), so there is no within-run marker. Whether run-boundary timing is
   precise enough for a lead-time analysis is the first thing to measure.
3. **There is no per-second responsiveness label**, so the "control" class would be defined by run identity
   rather than by a behavioural scale. DOSE-I's `SOC` agrees with `MOAAS > 1` on 98 % of samples; nothing
   comparable exists here, and a run-identity label is a coarser and more confoundable thing.

**Not queued as immediate work.** It rests on a deposit whose outcome column is already the subject of an
unsent request (Q11), it answers E24's question rather than E40's, and its landmark precision is unmeasured.
Recorded because E40's data-shape requirement generated it, and a requirement that generates a candidate is
worth more than one that only rules things out.

---

## Q16 — the covariate-adjusted normal reference, built from HEEDB negative reads

**Status: COHORT BUILT. The signal pass and the experiment that can kill the idea cheaply are next.**

`UCE_AND_THE_THREE_CHALLENGES.md` identified the frozen population reference as the one method the prior
work has that this project lacks, and the reason our results do not compose across deposits — every
experiment here normalises **within cohort**, which is why E39 could not combine `ds004541` and `chennu`
into one estimate and why E36's legibilities cannot be carried anywhere.

The investigator's proposal improves on the prior work's own reference in two ways, and both matter:

1. **A better population.** The prior reference was 1,170 BDSP **sleep-study** patients — people referred
   for suspected sleep pathology, not healthy people. HEEDB negative reads are routine clinical EEGs that
   an expert neurophysiologist read as **normal**.
2. **Conditional rather than pooled.** Adjusting for age, sex and comorbidity replaces one global centroid
   with an expected value **given the patient**. That is the principled version of "use the patient's own
   awake baseline", and it has the property that matters clinically: **it works where no baseline
   recording exists** — ICU, emergency, disorders of consciousness — which is exactly where the flagship
   applications are. The prior work's operating point moved from −0.30 to −2.09 across individuals; a
   conditional reference is the direct attack on that.

### What was built

`analysis/heedb_normal_reference_cohort.py`, metadata only, no signal read:

| | |
|---|---|
| recordings in the findings tables (S0001 + S0002) | 129,831 |
| `normal` flagged | 36,109 |
| **STRICT normal** (`normal` set **and** every abnormality column empty) | **4,944** |
| unique patients | **4,558** |
| joined to `HEEDB_ICD10_for_Neurology.csv` | **100 %** |
| with a `BidsFolder` (reachable in the BIDS store) | **99.6 %** |
| age | median 41, IQR 23–61, range **0–90** |
| sex | 2,472 F / 2,446 M |
| comorbidity | median 3 ICD chapters; **474 patients with none** |

**The strict definition is primary and the gap it opens is not a rounding detail.** A report can be
summarised "normal" while an annotation records focal slowing or a breach rhythm; 36,109 → 4,944 is what
that costs. A centroid built from recordings carrying documented abnormalities is not a normal reference,
and the only value this object has is that it can be trusted. The loose set is emitted by `--loose` as the
sensitivity arm.

Normal **variants** are deliberately kept — spindles, vertex waves, K-complexes, POSTS, PDR, wicket, BETS.
A normal EEG containing sleep spindles is still normal, and excluding them would select against anyone who
fell asleep in the department.

### Next, in order, and the second item can kill the idea for the price of one signal pass

1. **Signal pass**: aperiodic exponent (and the rest of the registry) over the 4,944 recordings, sharded,
   process-and-discard. Nothing patient-derived enters the repository — the cohort table already lives
   under `/tmp/eeg_probe/` and is gitignored.
2. **The experiment that decides whether any of this helps.** Fit `exponent ~ age + sex + comorbidity` on
   the reference cohort and ask **how much of the between-subject variance the covariates actually
   explain.** No outcome, no candidate, no label — a pure measurement-model question, and the same
   discipline E38 applied to E28's label: *characterise the instrument before claiming anything with it.*
   **If R² is trivial, a conditional reference is no better than a pooled one and the idea dies for the
   cost of one regression.** If it is substantial, the adjusted reference is worth freezing.
   Age must enter non-linearly — the aperiodic exponent's age dependence is well documented — so a spline
   or age bands, declared before the fit.
3. **Only then** freeze `(expected_exponent | covariates, residual_SD)` and re-express existing results on
   it, starting with one where the within-cohort normalisation is currently doing hidden work.

---

## Q17 — the band finding, and what it changes about Q16

**Status: EXPLORATORY, must be registered before it is claimed anywhere.**

E43 refuted the claim that a broadband spectral slope is EMG-robust — asymmetry **−0.0967 [−0.1886,
−0.0058]**, meaning it is *less* robust than BIS. The immediate question is what should go on a normative
scale instead. Same machinery, same 5,845 rows, case-clustered:

| measure | asymmetry (positive = more EMG-robust than BIS) |
|---|---|
| `exponent_high` (20–40 Hz) | **−0.1335 [−0.2317, −0.0524]** |
| `whole_head_exponent` (1–45 Hz) | **−0.0967 [−0.1886, −0.0058]** |
| `relative_alpha_power` | +0.0478 [−0.0409, +0.1335] |
| **`exponent_low` (1–20 Hz)** | **+0.1591 [+0.0714, +0.2384]** |
| **`lempel_ziv`** | **+0.1894 [+0.1109, +0.2662]** |

**The broadband exponent inherits its whole EMG vulnerability from the 20–40 Hz half.** Restricting the fit
to 1–20 Hz flips the sign.

**Why it is worth acting on while still exploratory:** two measures agree in sign with intervals excluding
zero; the ordering is monotone in how much of the EMG band the fit spans; and the mechanism is transparent
— surface EMG lives at 20–45 Hz, so a fit crossing it absorbs it. **Why it must still be registered:** it
is a post-hoc extension of E43 on the same rows, prompted by E43's own outcome, and six measures were
compared.

**Changes to Q16.** The normative scale should carry **`exponent_low`**, not the broadband exponent, and
`lempel_ziv` alongside it. The step-4 regression should be run on both, since they may have different
covariate structure. **This reverses the measure this project would have chosen a day ago, on measurement
rather than preference.**

**And it lands on an idea the prior work already had.** Its dual-slope decomposition (1–20 vs 20–45 Hz) was
used to separate ketamine from seizure; here the same decomposition solves an artefact problem. Two
independent reasons to carry both bands rather than one broadband number, and `subband_exponents` already
exists in the registry.
