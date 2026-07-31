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

> ### ANSWERED 2026-07-31, AND THE ANSWER IS YES — Q14 IS UNBLOCKED
>
> One session (`S39_Session_3.mat`, 480 MB, downloaded in 18 s through the figshare REST API) was read
> directly with `scipy.io.loadmat`. Verified, not inferred:
>
> * **`BCI.time` runs −2000 … +9040 ms at 1000 Hz**, i.e. **2.00 s of PRE-CUE BASELINE before every
>   trial**. At 450 trials that is **900 s = 15 minutes of task-free data per session**, which is more
>   resting EEG per session than most dedicated resting deposits carry per subject.
> * `BCI.data` — 450 trials × **62 channels** × 11,041 samples; channel labels are standard 10-10
>   (`FP1 FPZ FP2 AF3 AF4 F7 F5 F3 F1 FZ …`), so the project's 10-channel montage is present.
> * `BCI.TrialData` — `result` populated on 437 of 450 trials, mean 0.883; **0 artifact-flagged**.
> * `BCI.metadata` — `age` 21, `gender` F, `handedness` R, plus `meditationpractice`, `athlete`,
>   `instrument`. Demographics are per session as claimed.
>
> **So the label needs no signal at all** — `TrialData.result` gives per-session accuracy directly, which
> means Q14's step 2 (measure the reliability BEFORE the correlation) can run on metadata alone.
>
> ### A SECOND CHECK, AND IT NARROWS WHAT Q14 CAN DELIVER
>
> **Stieger CANNOT test `lrtc_alpha`, which is E42's marker and the one E56 studied.** The deposit is
> trial-epoched: 450 separate 11.04 s epochs (2.00 s pre-cue + 9.04 s task), with no continuous recording.
> `lrtc_envelope` needs scales to 20 s and had a guard that silently SHRANK its top scale to fit the
> segment — on a 2 s epoch, to 4.0 s. **It would have run, returned a plausible number, and that number
> would not have been comparable to any other `lrtc_alpha` in the project, with nothing in the output
> saying so.** Caught before the extractor was built.
>
> The guard is now a **refusal**: `lrtc_envelope` returns NaN when the required shrink exceeds a factor of
> 2 (`MAX_SCALE_SHRINK`). Recordings long enough for the requested range are unaffected — the branch never
> fires for them — so no existing result changes. Verified: 2 s → NaN, 11 s → NaN, 40 s → 0.532,
> 180 s → 0.463.
>
> **So Q14 delivers a better LABEL for SPECTRAL markers, not a successor to E42.** That is still worth
> having — E41's incumbent was spectral and E56 showed Challenge B is underpowered rather than answered —
> but it is a different experiment from the one Q14 was written to enable, and the write-up must not
> present it as a replication of E42 on better data.
>
> **One caveat that must ride with any use of the baseline.** A 2 s pre-cue window inside a task block is
> not the same object as Blankertz's *"relax with eyes open"* recording: the subject is cued, engaged and
> between trials, not at rest. It is a legitimate task-free segment and it is NOT a resting-state
> recording, and any comparison to Blankertz's incumbent inherits that difference.

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

---

## Q18 — the existing-normative-model question, answered; three items fall out of it

*Added 2026-07-31. Full record and verification trail: `bsde/docs/EXISTING_NORMATIVE_MODELS.md`.*

**Answer: six validated normative EEG systems exist and none is usable as our reference.** The best-validated
are commercial (NeuroGuide, Neurometrics, BrainDx, SKIL, qEEG-Pro — the last FDA-approved); the two best
academic ones (ISB-NormDB n=1,289 with explicit sex-differentiated models, Taiwan n=260) release data on
request only; and **not one of the six models an aperiodic measure.** The PubMed intersection of
normative-modelling terms with aperiodic/spectral-exponent returns **13 hits, all of which use "normative"
descriptively rather than as a resource.**

**Q18a — decide on HarMNqEEG (needs an investigator decision, cannot be done unilaterally).** PMID 35398285:
1,564 subjects, 9 countries, 12 devices, 14 studies; open **cross-spectral tensors** on Synapse
`syn26712693` (verified live: `ShareRawData` → 14 named study folders → per-subject `.mat`). Anonymous
download returns HTTP 403 — a **free Synapse account** is required. Worth it because PMID 42040156 already
estimated **aperiodic components on 1,965 HarMNqEEG subjects aged 5–100**, so the deposit demonstrably
supports our measure. It would be the external validation set for a HEEDB-derived reference.
*Unverified and must be checked before relying on it: whether **sex** is a term in HarMNqEEG's
mixed-effects equations. The abstract names age only and the paper is not open access.*

**Q18b — pull OpenNeuro `ds005385` (no gate, do it).** Dortmund Vital Study, verified through the OpenNeuro
GraphQL API: **608 subjects, age 20–70 (137/111/111/140/95/14 by decade), 376 F / 232 M**, handedness, two
sessions **~5 years apart**, 17,541 files, 79.5 GB, no credentials. Gives an independent adult age+sex
reference *and* lets us reproduce the exponent's five-year ICC on our own estimator instead of citing it.
Limits: healthy volunteers (so it does not substitute for HEEDB's acquisition-matching argument) and it
stops at 70 where HEEDB reaches 90.

**Q18c — two numbers that change Q16 and must be carried into it.**
1. **Eyes open/closed moves the exponent by d = −0.761** (PMID 42395346). That is larger than any
   comorbidity effect and larger than the medication effect Q16 is built around; HEEDB does not record it.
   **Promoted out of "known unknowns" — the wake detector and the eye-state detector are now one frozen
   object.** Five-year ICC of the exponent is 0.668 (trait ceiling ≈ 0.82, well above anything we are
   chasing), and 2–3 minute recordings suffice (PMID 38820994, PMID 32425762) — so the reference does not
   need long segments.
2. **Aperiodic correction can produce age-independence** — corrected theta/alpha scored r = 0.000 against
   age in 587 adults (PMID 42294963). R² ≈ 0 means **zero** Challenge B gain via 1/sqrt(1−R²).
   **Q16 step 4 must therefore be run separately for `exponent_low` and `lempel_ziv`, never pooled.**

---

## Q19 — REQUEST BDSP ACCESS TO LENS (investigator action; nothing else here is blocked on it)

*Added 2026-07-31 after a prior-art audit found the project had already named this deposit and the search
that answered "is there an existing normative model?" never checked internally.*

**LENS — "Lifespan and Sleep-Stage-Resolved Normative EEG Background"**, on BDSP, named in
`MASTER_PLAN.md` §3.1 and §9.28 as *"a genuine normative reference"* and *"the deposit to pursue"*, lifespan
rather than paediatric.

**Probed 2026-07-31 and it is NOT reachable with current credentials** — absent from
`bdsp-credentialed-access-point`, `bdsp-credentialed-projects-ap` and `bdsp-restricted-access-point`, and
absent from `EEG/` and `PSG/` one level down. A separate access request is required.

**Why it matters and what it does not settle.** It is on the same platform as HEEDB, so a granted request
costs no new infrastructure, and it is lifespan-scoped, which is exactly what the adult-only open cohorts
are not. **What is unknown is whether it carries an aperiodic measure** — no public normative database does
(§1 of `EXISTING_NORMATIVE_MODELS.md`), and LENS's contents are unverified here. So it may be a reference
for band power that still leaves the exponent unnormed, which is the situation the whole multi-cohort build
exists to address. Request it, but do not plan around it.

---

## Q20 — chennu CANNOT be re-extracted from this sandbox (environment blocker, not a design problem)

*Added 2026-07-31. The script is written, correct and committed; the host is unreachable.*

E52 confirmed E50's prediction but carries one asymmetry: chennu's sub-bands come from the older
per-deposit extraction and ds005620's from `analysis/eeg_features_common.py`. The estimator is identical
(`subband_exponents`) but the montage, the 180 s window and the 250 Hz resample are not. `exponent_high`
agreed to **0.006** across that difference — either strong evidence it is immaterial, or luck at n = 20.

`analysis/chennu_shared_extract.py` removes the ambiguity and **cannot run here.**
`api.repository.cam.ac.uk` fails TLS with *"Hostname mismatch, certificate is not valid for
api.repository.cam.ac.uk"* under both `curl --cacert /root/.ccr/ca-bundle.crt` and Python with
`SSL_CERT_FILE`/`REQUESTS_CA_BUNDLE` set. It is **host-specific, not a proxy misconfiguration**: measured
the same minute, `s3.amazonaws.com` returns 307 and `eutils.ncbi.nlm.nih.gov` returns 301, while both
`api.repository.cam.ac.uk` and `repository.cam.ac.uk` return 000. Disabling TLS verification or unsetting
`HTTPS_PROXY` is forbidden by the environment rules and was not attempted.

**So the existing `chennu_features_v3.csv` cannot be regenerated in this sandbox** and E52's asymmetry
cannot be closed the direct way here.

**Two things that CAN be done instead, in order of value:**

1. **Measure the asymmetry rather than eliminate it.** Process ds005620 through the shared path *and*
   through a chennu-matched configuration (average reference, the deposit's epoching, 0.5–45 Hz), and
   report how far the sub-band displacements move. If they move far less than the 0.006 agreement, the
   asymmetry is immaterial and E52 stands without chennu being touched. This needs no new access.
2. **Re-extract ds004541 through the shared path** (OpenNeuro, reachable) to add a third deposit to E49's
   sub-band re-run. It cannot fix the chennu asymmetry and its agent is unrecorded, so it anchors the
   state scale only — but it is the only way to get past two deposits with current access.

---

## Q21 — the HEEDB vigilance metadata cannot replace an in-signal detector, but it supplies its validation set

*Probe run 2026-07-31 before committing to the reference build (rule 41). No shortcut found; a validation
set found instead.*

**The hope.** HEEDB's findings table carries `pdr` — posterior dominant rhythm, i.e. the alpha rhythm that
appears specifically when a subject is **awake with eyes closed**. E44 has just measured eye state at
d_z = −1.214 on `exponent_low`, making it a first-order term the reference must control. If `pdr` selected
awake-eyes-closed recordings from metadata alone, the reference build would skip building a detector.

**Measured on all 4,944 strict-normal recordings:**

| flag | n | % |
|---|---|---|
| `n1` | 4,487 | 90.8 % |
| `awake` | 4,270 | 86.4 % |
| `pdr` | 3,988 | 80.7 % |
| `awake` **and** `pdr` | 3,699 | 74.8 % |
| `n2` | 3,156 | 63.8 % |
| **`pdr` and NO sleep marker** | **186** | **3.8 %** |

**The shortcut fails.** Requiring PDR present and no sleep marker leaves 186 recordings — essentially the
202 found earlier by a different route. The flags are **recording-level**: they record that a recording
*contains* PDR and *contains* N2, not *when*. 90.8 % contain N1. **The in-signal detector is unavoidable**,
which is what §1 of `NORMAL_REFERENCE_COVARIATES.md` concluded and this probe now confirms by measurement
rather than by inference.

**What the probe did buy, and it is not nothing.** §1 assigned the recording-level flags the role of *"a
coarse check on that detection"* without saying what the check would be. Now it is concrete: **3,699
recordings are flagged BOTH `awake` and `pdr`**, and 956 carry no `pdr` at all. A wake/eyes-closed detector
must find PDR-bearing awake segments in the first group at a far higher rate than in the second. That is a
labelled validation set for the detector, obtained from metadata already held, at zero extraction cost —
and a detector that cannot separate those two groups should not be frozen into anything.

---

## Q22 — BIS IS NOW COMPUTABLE, AND IT REMOVES CHALLENGE C's LARGEST STRUCTURAL LIMIT

*Added 2026-07-31 on the investigator's prompt. Every record below pulled through E-utilities and
Europe PMC with `curl` and read, never a fetch-tool summary (rules 25, 39).*

**Why this matters more than any other open item for Challenge C.** E26, E34 and E37 all scoped themselves
*"never ahead of BIS"* and used **SEF95 as a proxy** — not by preference but because **BIS exists only on
VitalDB**, where a monitor recorded it. E46 and E55 are the only experiments that ever compared against
real BIS, and both are confined to 250 VitalDB cases, two frontal channels, maintenance only. **If BIS can
be computed from arbitrary EEG, it becomes a universal comparator and every one of those constraints
lifts.**

### Two independent routes, both verified to exist

1. **Connor CW, "Open Reimplementation of the BIS Algorithms for Depth of Anesthesia", *Anesth Analg*
   2022 — PMID 35767469, PMC9481655.** In the author's words: *"the algorithms used by such monitors
   remain proprietary. **We do not actually know what we are measuring**… an A-2000 BIS monitor was
   forensically disassembled and its algorithms (the BIS Engine) retrieved as machine code. Development of
   an emulator allowed **BIS scores to be calculated from arbitrary EEG data for the first time**."*
   The authoritative route. **Code availability is NOT established here** — the article is in PMC but not
   open access and Europe PMC returned no full text, so obtaining the emulator is an unresolved step.

2. **Lee HC, Ryu HG, … Jung CW, "Data Driven Investigation of Bispectral Index Algorithm", *Sci Rep*
   2019 — PMID 31551487, PMC6760206, OPEN ACCESS.** 5,427 patients; decision tree plus range-specific
   regression models; **median absolute error 4.1 BIS units**. **These authors are the VitalDB team**, so
   the models were derived on data of exactly the kind this project already holds.

### What BIS is actually made of, which is most of what we already emit

*"BIS values are known to be calculated from four EEG subparameters, burst suppression ratio (BSR), QUAZI
suppression index, relative beta ratio (RBR), and SyncFastSlow (SFS)"* — and Lee et al.'s own tree uses
**BSR, EMG power, SEF95 and relative beta ratio**.

| subparameter | status in this repo |
|---|---|
| burst suppression ratio | the sibling burst-suppression programme is built on exactly this machinery |
| 95 % spectral edge | already emitted as `sef95` |
| relative beta ratio | trivial from the existing PSD |
| EMG power | already emitted — `emg_index`, `emg_beta_gamma_fraction`, `emg_kurtosis` |
| SyncFastSlow | bispectral, needs implementing |
| QUAZI suppression index | suppression-related, partly available |

### The plan, and it has a validation step that is free

1. Implement a BIS-like index from the published subparameters.
2. **VALIDATE IT AGAINST THE REAL THING ON OUR OWN DATA — this is the part that makes the whole idea
   safe.** `vitaldb_grid.csv` holds **5,845 windows with paired EEG and DEVICE BIS**. Agreement can be
   measured directly, in BIS units, against a hardware ground truth. No other deposit is needed and no new
   access is required.
3. Only if agreement is adequate, apply it to the deposits that have no BIS at all: chennu, ds005620,
   ds004541, HEEDB (0–90), ds005385 (608 subjects with known eye state).

### What it would unlock, concretely

* **E55 on a real age range.** E55 found that at matched BIS the EEG state differs by age, on 240 VitalDB
  cases. HEEDB spans **0–90 with age SD 24.1 years** and E57 measured age+sex R² there at **0.2547**
  against 0.0877 in the open adult cohorts — roughly three times the age signal. The age-neutrality claim
  would get a far stronger test.
* **E26/E34/E37 redone against the intended comparator** rather than the SEF95 proxy they settled for.
* **A verifier target rather than a black box.** Connor's own framing — *"we do not actually know what we
  are measuring"* — is precisely the gap this project's verifier exists to close.

### FEASIBILITY PROBED 2026-07-31 (rule 41) — a reimplementation is worth building

Before writing any BIS reimplementation, the cheap question: **how much fidelity is reachable from
subparameters this repo ALREADY computes?** 5,828 maintenance windows with device BIS, sensor attached,
247 cases. **Case-grouped 5-fold CV** — windows within a case are highly correlated, so ungrouped folds
would leak and inflate every number below.

| arm | median \|err\| (BIS units) | mean \|err\| | R² |
|---|---|---|---|
| **OURS — every feature computed by us from raw EEG** | **5.01** | 7.55 | 0.274 |
| OURS + device BSR (`meta_sr`) | 4.92 | 7.02 | 0.380 |
| **DEVICE subparameters only (`meta_sr`, `meta_emg`)** | **6.15** | 7.94 | 0.350 |
| OURS + device BSR + device EMG | 4.56 | 6.38 | 0.496 |

**Lee et al. report median absolute error 4.1 on their own development data.** Our features reach **5.01**
— and they were never designed for this, are computed on two frontal channels at 128 Hz, and are **missing
three of the four real BIS ingredients** (SyncFastSlow, QUAZI, relative beta ratio).

**The surprise: our independently computed features predict device BIS BETTER than the device's own
reported subparameters do** — 5.01 against 6.15. Whatever `meta_sr` and `meta_emg` are, they are not a
sufficient basis for the index the same monitor reports.

**Verdict: build it.** Adding the three missing ingredients should close most of the remaining gap, and a
range-specific model (as Lee used) rather than one linear fit should close more.

**What this probe does NOT establish, and it is the caveat that matters most.** These windows are
maintenance only: device BIS has median 42.1 and IQR 36.1–49.6. **So 5.01 is fidelity INSIDE the target
band, across a range of about 14 BIS units.** Fidelity at the light and deep extremes is untested here and
cannot be tested on this deposit — which is exactly the per-range reporting the third caveat below demands.
Mean error 7.55 against median 5.01 also shows a tail of poor predictions that a headline median hides.

### Three caveats that must ride with it

* **A reimplementation is not BIS.** Lee et al. report median absolute error 4.1 on their own development
  data; ours would be worse. Any result must state the measured fidelity, not assume it.
* **Provenance.** Route 1 derives from forensic disassembly of a commercial device. That is what the
  published work did and it is citable, but it needs care in anything intended for publication.
* **Fidelity is not uniform.** Lee et al. fit *range-specific* models, so agreement almost certainly varies
  with depth — and the deep and light extremes are exactly where a depth monitor's disagreements matter.
  Fidelity must be reported per BIS range, not pooled.

### E58 BUILT IT AND MEASURED IT, 2026-07-31 — the answer is "yes inside the target band, no outside it"

`vitaldb_bis.csv` now exists: the four subparameters (`bis_rbr`, `bis_bsr`, `bis_quazi`, `bis_sfs`) computed
on the **same 6,679-window grid** `vitaldb_grid.csv` covers, joined at **100.0 %** with **zero** `meta_bis`
disagreements. Analysis set 5,845 windows, 247 cases. `bsde/src/bsde/features/bis_subparams.py` implements
them from the published descriptions; SyncFastSlow is the first genuinely bispectral quantity in this repo.

**The registered primary said NO GAIN, and it was close.** Out-of-bag median |err| increment for
ours+subparams over ours alone: **−0.195 BIS units [−0.424, +0.035]** across 400 refit draws. The point
estimate favours the subparameters; the interval does not exclude zero; the rule was written first and is
not being moved (rule 30). The within-case placebo returned **+0.004 [−0.079, +0.085]**, a tight null, so
the −0.195 is genuine window-level tracking rather than four extra columns of case-level information —
an *underpowered positive*, not a flat nothing.

| arm | median \|err\| | mean \|err\| | R² |
|---|---|---|---|
| A ours (15 live features of 18; 3 are all-NaN on one channel) | 4.81 | 7.18 | 0.343 |
| B the four subparameters alone | 6.80 | 9.21 | 0.142 |
| **C ours + subparameters** | **4.60** | **6.86** | **0.407** |
| D device's own SR + EMG | 6.28 | 8.46 | 0.246 |
| E everything | 4.52 | 6.57 | 0.450 |

The probe's central surprise survives at higher precision: **features computed independently from raw EEG
predict device BIS better than the device's own reported subparameters** — 4.81 against 6.28.

**THE PER-BAND TABLE IS THE RESULT, NOT THE PRIMARY.** Arm C, evaluation-stratified by device BIS:

| device BIS | n | median \|err\| | mean \|err\| |
|---|---|---|---|
| [0,40) | 2,330 | 5.48 | 7.64 |
| **[40,60) target band** | 2,879 | **3.47** | 4.38 |
| [60,80) | 468 | 8.75 | 9.96 |
| **[80,100)** | **168** | **29.84** | 29.76 |

Inside the clinical target band the reimplementation beats Lee et al.'s 4.1 on their own development data.
Q22's third caveat predicted non-uniformity; this is far worse than non-uniform.

**WHAT THE [80,100) ROW MEANS, AND THE FIRST READING OF IT WAS WRONG.** The obvious sentence — "at BIS ≥ 80
the index is worthless, in exactly the band where a monitor exists to warn that a patient is awake" — was
written here and is **withdrawn**, because **E22 closed at its gate on precisely this population: every
BIS ≥ 80 window in VitalDB is a facial-EMG artefact.** Re-measured independently inside E58's own analysis
set rather than taken from E22: **98.2 %** of those 168 windows exceed E46's artefact threshold
(`meta_emg` ≥ 32.3), median EMG **48.6** against ~26.8 in the target band, and median SQI falls to **69.9**
from 93.7. So that row does not measure failure to detect wakefulness. It measures **failure to reproduce a
device reading that is itself being driven by muscle** — and a from-scratch index computed from EEG has no
mechanism to reproduce it, which is a property of the reference, not a defect of the index. Giving the model
the device's own EMG channel (arm E) recovers **5.1** of the ~30 units and no more, so EMG is part of the
story and a single global linear fit does not capture the rest.

The correction makes the deposit's limit sharper rather than softer: **VitalDB contains no genuine
awake-under-monitor windows at all.** The strip goes on after induction and comes off around emergence, so
fidelity at the light end is not merely undermeasured here — it is untestable here, and 168 more windows of
the same kind would not help.

**WHAT THIS LICENCES.** Computing the index on monitor-free deposits (chennu, ds005620, ds004541, HEEDB,
ds005385) **only for windows whose predicted value lands in [40,60), and always with ±3.47 attached.** Any
use at the light end is unsupported by measurement and must not be made. That is a narrower licence than
step 3 of the plan above assumed, and it is the honest one.

**M2 fired the way the registration expected without failing.** `bis_bsr` passed the variance gate but only
**7.44 %** of maintenance windows carry any suppression at all — the stratum is nearly degenerate for the
predicted reason (rule 32). Two declared failure conditions were tested and not met: `bis_bsr` agrees in
direction with the device's own BIS/SR track (Spearman **0.410**, n=5,798), and `bis_quazi` is not a second
copy of `bis_bsr` (Pearson **0.050**) — the increment definition did its job (rule 28).

**Registering median |err| as the primary was the wrong choice and is now error-catalogue rule 51.** It is
the statistic least sensitive to a tail, and the tail was the whole finding.

#### What is still open

* **A range-specific model selected from a first-pass PREDICTION, not from the true BIS.** E58 deliberately
  refused to fit range-specific models because the range is defined by the regression target and choosing
  the model from the target's true value is leakage. A two-stage version — predict, then refit within
  predicted range — is legitimate and untried. It would attack the [60,80) band, where median |err| is 8.75
  on 468 windows with 35 % artefact contamination. It should **not** be aimed at [80,100): chasing a target
  that is 98.2 % muscle would fit the artefact, not the index.
* **A light-anaesthesia deposit.** VitalDB structurally contains no awake-under-monitor windows, so fidelity
  above BIS 80 is untestable here — not undermeasured, untestable. This is the same wall E22 hit and it is
  now blocking two experiments, which raises the value of any deposit carrying EEG plus a depth monitor
  through induction or emergence.
* **Whether the index needs to be BIS-faithful at all.** The reference at the light end is muscle. A
  comparator that reproduces BIS *including* its artefacts is not obviously more useful for Challenge C
  than one that tracks BIS in the band where BIS is measuring brain. Worth deciding explicitly before the
  index is used anywhere, rather than defaulting to "closer to BIS is better".

---

## Q23 — SyncFastSlow validated against an independent implementation (E59, 2026-07-31), and what it revealed about BIS

`sync_fast_slow` was the only genuinely new machinery E58 introduced, and its 18 tests were all mine — rule
23's exact hazard. **DOSE-I ships an independent implementation**, and its `pEEG_parameter_description.txt`
fixes the sign before any data is touched: their SynchFastSlow is the quotient **40-47 Hz over 1-47 Hz**, the
reciprocal of the Rampil form implemented here, so the two must run opposite ways.

**VERDICT: AGREE.** Median within-recording Spearman(ours, theirs) = **−0.5875 [−0.6466, −0.5309]** over 38
recordings and 12,469 windows. The placebo — our series circularly shifted 600 s inside its own recording,
preserving every marginal and every autocorrelation — gives **+0.0339 [−0.0248, +0.1363]**, flat. This clears
the **computational** verifier layer for `bis_sfs`, which is the only layer its declaration requires, and
nothing else.

### The finding worth more than the verdict

DOSE-I also ships **PowerFastSlow**: a pure power ratio over the *identical bands*. Partialling it out takes
the agreement from −0.5875 to **−0.2706 [−0.3496, −0.2327]** — reduced by more than half, and **still
decisively excluding zero**.

So: a real bispectrum-specific component exists, and it is smaller than the component shared with plain
power. **This is the first empirical statement in this project about how much of SyncFastSlow is bispectral
rather than spectral — the distinction BIS's name rests on.** It also explains E58's null without appeal to
anything else: adding `bis_sfs` to a feature set already rich in spectral measures buys little precisely
because most of what it carries is spectral.

*(The experiment's printed NOTE says the two "may be tracking power rather than phase coupling". That is the
harsher of the two readings the numbers allow and they do not require it — the partial correlation excludes
zero. The accurate statement is the one above.)*

### Exclusions, reported (rule 14)

**21 of 60** attempted recordings were refused by the extractor's uniform-time-axis check. Two were examined
directly: `10-011` carries an **82.8 s** hole among 4 gaps; `10-030` carries 13 gaps totalling **15.7 s**.
The gaps are real and the refusal is correct — a uniform axis would have misaligned every window after the
hole against the depositors' 1 Hz series (rule 27). The criterion reads only the raw file's timestamps and
cannot see either SFS series, so it cannot be related to the agreement statistic. **A gap-aware extractor
would recover roughly a third more recordings** and is the obvious next improvement.

### A probe was run that spent the directional question on this deposit

Before E59 was registered, a feasibility probe read the depositors' SFS and PFS against per-second SOC across
all 171 recordings. Reported as a **probe, descriptive, not a registered test**:

* within-recording Spearman(SFS, PFS) median **+0.737** (IQR +0.592…+0.845), pooled +0.797 — consistent with
  what E59 then measured against our own implementation;
* SFS median **−3.027** conscious vs **−3.898** unconscious; PFS **−1.514** vs **−2.045**.

Under DOSE-I's convention unconsciousness lowers both, so under this repo's reciprocal convention it raises
`bis_sfs` — the direction its declaration committed to. **That agreement is NOT a passed test.** The number
was seen before any prediction about this deposit could be registered, so `bis_sfs`'s direction stays
**untested**, and must be tested on a deposit nobody has looked at.

---

## Q22 CLOSED (E60, 2026-07-31) — the range-specific model works, and finding out cost two lessons

Q22's last open technical item was a two-stage model selecting its range from a first-pass PREDICTION rather
than from the true BIS (which would be leakage). **E60 ran it. VERDICT: GAIN.**

Median |err| on true BIS ∈ [0,40), two-stage minus one-stage: **−0.635 [−1.035, −0.203]** over 400 out-of-bag
draws with both models refitted per draw. Point estimates **5.482 → 4.764**. The placebo — a random partition
of identical sizes, same sub-model count, same parameter budget, no range information — returns
**+0.020 [−0.167, +0.248]**, flat. So it is range specificity, not extra parameters.

**The target band moved twice before this ran and the registration says so rather than drifting:** Q22 aimed
it at [80,100); the BIS-faithfulness decision redirected it to [60,80) at most; E60 redirected once more to
[0,40), because [60,80) is itself 35 % artefact and the decision's own rule leaves only the two clean bands.
[0,40) is where the global fit did worst among them, on 2,330 windows, and is where a separate relationship
is expected physiologically — burst suppression exists there and nowhere else.

### It is a reallocation, not a free improvement

Descriptive slicing after the run: [20,30) 9.69 → 8.88, [30,35) 6.15 → 5.14, [35,40) 3.37 → 2.82 — the gain
is spread across the band rather than sitting at its boundary. **But [40,60) goes 3.47 → 3.91, worse by 0.44
on 2,879 windows.** The registration fixed the falsification condition to [0,40) "and nowhere else", which
correctly stopped the bar moving — and equally stopped the experiment from seeing what it gave up. **Error
catalogue rule 52.** The deliverable therefore uses the one-stage fit in [40,60) and the two-stage fit below
it; quoting one model for both bands would misreport one of them.

### The finding that is not about the model at all

**[0,20) carries median |err| 39.96 under BOTH models** — neither touches it — on 90 windows from 68 cases.
Its median **SQI is 5.1 out of 100**. The device is reporting a BIS value it simultaneously flags as almost
entirely unreliable, with EMG elevated at 38.2.

This is the **mirror image of the [80,100) finding at the other end of the scale**: not a deep-anaesthesia
population the index fails on, but a population where the *reference* has collapsed. E58's inclusion
criterion was BIS present and sensor not off; **`meta_sqi` shipped in the same table from the start and no
experiment had used it.** E58's and E60's verdicts stand as registered and their errors are, if anything,
pessimistic in those bands — but the deliverable index's error bars should be quoted from an SQI-filtered
cohort, registered separately, because changing inclusion after seeing results is a change of cohort and not
a footnote.

### Where Q22 finishes

| band | model | fidelity | status |
|---|---|---|---|
| [0,20) | either | 39.96 | **refuse** — median SQI 5.1; the monitor disowns its own reading |
| [20,40) | two-stage | ~4.8 | usable |
| [40,60) | one-stage | **3.47** | usable; beats Lee et al.'s 4.1 on their own development data |
| [60,80) | — | 8.75 | **refuse** — 35 % facial-EMG artefact |
| [80,100) | — | 29.84 | **refuse** — 98.2 % facial-EMG artefact |

---

## Q24 — Challenge A: propofol and sevoflurane are not legible at matched depth, so VitalDB cannot test E36's split (E61, 2026-07-31)

E36 found phase-based coupling measures leak far less anaesthetic identity than power/complexity ones
(|AUC−0.5| 0.000–0.128 vs 0.217–0.368), as the unique maximum of 495 same-size partitions. `bis_sfs` — the
bispectrum built for Q22 and validated in E59 — made a **within-channel** version of that test possible on
VitalDB, where E36's inter-channel wPLI is NaN.

**VERDICT: NO SPLIT.** Phase minus amplitude = **−0.0116 [−0.0589, +0.1273]**; the real 2-vs-7 partition
ranks **14 of 36** (p = 0.389) against E36's p = 0.002. Both gates passed.

### The diagnostic that changes what the null means

A permutation null run afterwards — agent label shuffled across cases, 60 draws, same statistic — shows
**not one of the nine candidates leaks above its own null**:

| | observed \|AUC−0.5\| | null mean | p(≥obs) |
|---|---|---|---|
| phase family | 0.0787 | 0.1011 | 0.800 |
| **amplitude family** | **0.0903** | **0.0960** | **0.583** |
| largest single (whole_head_exponent) | 0.1438 | 0.0989 | 0.233 |

**The amplitude family sits below its own null mean.** So the substantive finding is not about families:
**at matched BIS, propofol and sevoflurane are not legible from any of these nine frontal measures**,
out-of-fold with cases held out whole. That is a clean negative, mildly *favourable* to Challenge A — and it
means this cohort cannot test E36's split, because a contrast needs at least one family to show the effect.
**Error catalogue rule 53**, and the gate already existed here: E33's "the incumbent must be alive".

### Why no VitalDB pairing escapes it

E36's leak was propofol vs **dexmedetomidine**, an α2 agonist producing a pharmacologically distinct
sleep-like state. This is propofol vs sevoflurane — both GABAergic. The remaining pairs are
desflurane/propofol and sevoflurane/desflurane: same class, or volatile against volatile. **Challenge A's
family question needs a pharmacologically distinct agent, and this deposit has none.**

That raises the priority of two items already in the queue and lowers the value of further VitalDB work on
Challenge A:

* **Q2 — the Dryad ketamine set.** Ketamine is the dissociation this project has been hunting: unresponsive
  with preserved experience, and NMDA rather than GABA.
* **The Turku/Kallionpää cohort** (47 volunteers, dexmedetomidine *or* propofol, **within-subject** loss and
  return at constant dosing). `DATA_REQUEST_TURKU_KALLIONPAA.md` is drafted and **unsent** — this result is
  the argument for sending it.

---

## Q25 — Challenge C's two failure modes are different, and both are now measured (E62, 2026-07-31)

E60 found the BIS-like index scores median |err| 39.96 below BIS 20 under both models, with median
**SQI 5.1 of 100**. E62 asked whether that is the index's failure or the reference's, with a differential
prediction: under *reference collapse*, filtering on the monitor's own quality flag should strip the deep
band's error and leave [40,60) alone; under *index failure*, it should change little anywhere.

**The survival gate answered it before the primary could run.**

| band | windows at SQI ≥ 50 | cases | median SQI |
|---|---|---|---|
| **[0,20)** | 90 → **14 (15.6 %)** | 10 | **5.1** |
| [20,40) | 2,240 → 2,138 (95.4 %) | 228 | 91.7 |
| [40,60) | 2,879 → 2,792 (97.0 %) | 240 | 93.7 |
| [60,80) | 468 → 448 (95.7 %) | 183 | 91.6 |
| [80,100) | 168 → 133 (79.2 %) | 93 | 69.9 |

**VERDICT: BAND EMPTIED.** 84.4 % of the [0,20) windows fail the device's own flag, against 3–5 % in every
band from 20 to 80. The gate required 30 windows and 15 cases and got 14 and 10, so **no fidelity was
computed on the remnant and none may be quoted.** That refusal is the result, and it is stronger than a
number would have been: E60's 39.96 was the index being scored against readings the monitor declares
unreliable.

### The completed picture, with a different measured criterion at each end

* **Bottom fails on SIGNAL QUALITY** — 84.4 % of [0,20) below SQI 50.
* **Top fails on MUSCLE** — 98.2 % of [80,100) and 35.0 % of [60,80) above E46's EMG threshold, while both
  bands retain 79–96 % of their windows under the SQI filter. **Their failure is not a quality-flag
  failure**, so the two diagnoses do not substitute for one another and both had to be measured.
* **Middle, [20,60), is clean on both** — 95–97 % SQI survival, 4.6–5.6 % artefact.

### What was deliberately not done

Filtered fidelities for the usable bands were **not** computed: the registered gate stopped the experiment,
and continuing past a fired gate is what the gate exists to prevent. The retention figures mean E58's and
E60's published numbers already rest on a cohort that is ≥ 95 % SQI-clean in [20,60), so they stand as
quoted. A filtered refit is a one-line successor and has not been run.

### The deliverable, final

| band | model | fidelity | why |
|---|---|---|---|
| [0,20) | — | **refuse** | 84.4 % of windows fail the monitor's own SQI flag |
| [20,40) | two-stage (E60) | ~4.8 | 95.4 % SQI-clean, 5.6 % artefact |
| [40,60) | one-stage (E58) | **3.47** | 97.0 % SQI-clean, 4.6 % artefact; beats Lee et al.'s 4.1 |
| [60,80) | — | **refuse** | 35.0 % facial-EMG artefact |
| [80,100) | — | **refuse** | 98.2 % facial-EMG artefact |

---

## Q26 — Challenge A is CLOSED on VitalDB, measured from three directions (E64, 2026-07-31)

The consolidation round's rank-1 item was the two-channel test of E36's family split against Akeju. It was
built, probed, narrowed, registered and run in that order — and the answer is that **this deposit cannot
answer the question at all.**

### The probe killed the family comparison before registration (rule 41)

Over 4,220 usable windows on the newly extracted `vitaldb_conn.csv`:

| | median | sd | IQR | ρ vs BIS |
|---|---|---|---|---|
| `coherence_theta` | 0.6445 | 0.1655 | 0.5396…0.7337 | −0.0860 |
| `coherence_alpha` | 0.6606 | 0.1612 | 0.5527…0.7481 | −0.0633 |
| `wpli_theta` | **0.0106** | 0.1508 | **−0.0052…0.0549** | −0.0166 |
| `wpli_alpha` | **0.0235** | 0.1339 | **−0.0021…0.0913** | −0.0364 |

**wPLI is a noise distribution in every band** — centred on zero, symmetric, |ρ| with the monitor never
above 0.05. Two electrodes ~2 cm apart on a shared reference have no consistent phase lag, which is exactly
what wPLI measures. Coherence varies but sits at 0.60–0.66 in *every* band with no band structure: a shared
reference, not frontal network coupling. **E36's split is permanently untestable here.**

### What was registered instead, and what happened

Akeju's claim is a band **differential** with its own control — sevoflurane shows a theta signature propofol
lacks, while alpha is effectively identical (0.73 vs 0.71). A differential is the one statistic a
reference-dominated coherence can support, since the shared contribution cancels.

**M1 fired first: `coherence_theta` scored \|AUC−0.5\| = 0.0275 against its own permutation null (mean
0.1170, p95 0.1893), p = 0.967 — below chance.** No differential was computed. `coherence_alpha` (0.1144),
`wpli_theta` (0.1417) and `wpli_alpha` (0.1406) are all at or inside the same null.

### Three independent reasons, all measured

1. **Disjoint patients** — 0 of 247 cases carry more than one agent.
2. **Both drugs are GABAergic**, and Akeju *reports* alpha power and coherence as essentially identical
   between them with no significant slow-oscillation difference. The published expectation is that most
   measures should not separate them.
3. **The montage is a two-electrode strip**, supporting neither wPLI nor band-specific coherence.

Thirteen measures across five families — amplitude, complexity, within-channel phase, inter-channel
coherence, inter-channel wPLI — have now failed to separate propofol from sevoflurane at matched BIS, none
clearing its own null (E61 + E64).

**This is a property of the deposit, not a failure of any measure, and not evidence against E36.** Challenge
A now needs a pharmacologically distinct agent, and the two routes are already written: **Q2 (Dryad
ketamine)** and the **Turku/Kallionpää dexmedetomidine cohort**, whose request is drafted and *still unsent*.
Sending it is the highest-value Challenge A action available.

---

## Q27 — the ketamine deposit is worth MORE than Q2 claimed, and it cannot be fetched from this sandbox

**Q2 undersold it.** The Dryad record (`10.5061/dryad.j9kd51c9q`, CC0, 0.934 GB, one zip) was read through the
Dryad v2 API with `curl` and parsed from JSON (rules 25, 39). It is **Farnes et al., PLOS ONE** — *"Increased
signal diversity/complexity of spontaneous EEG, but not evoked EEG responses, in ketamine-induced psychedelic
state in humans"* — and the design is far better than "n = 10, sub-anaesthetic" suggests:

* **high-density 62-channel EEG** — so inter-channel wPLI and coherence are properly computable, which is
  exactly what VitalDB's two-electrode strip could not support (Q26);
* **within-subject, open-label, before AND during** ketamine in the same 10 volunteers — removing every
  between-subject confound that closed Challenge A on VitalDB;
* spontaneous EEG recorded **eyes open AND eyes closed**, so E44's first-order eye-state effect is a
  controlled variable rather than a lurking one;
* TMS-evoked responses with PCI alongside.

### The design it would unlock, and it does not need a second drug

Challenge A's acceptance condition needs a measure that follows STATE and not DRUG. This deposit supplies
**two contrasts in the same subjects and session**: the ketamine effect (drug) and the eyes-open/closed
effect (a non-drug arousal change). **The ratio of drug-response to state-response, per measure family, is
Challenge A's acceptance condition made testable without ever needing two drugs** — and E36's family split
becomes testable on a montage that can actually carry it.

### The blocker, and it is environmental

**`datadryad.org` is behind Anubis**, a proof-of-work anti-scraping challenge. The v2 API download endpoint
returns **401**, `/downloads/file_stream/…` returns an **HTML interstitial** whose own text says it exists
*"to protect the server against the scourge of AI companies aggressively scraping websites"*. That is a
deliberate access control by the data host, and **defeating it is not on the table** regardless of the CC0
licence on the content.

This is the same *shape* as Q20 (chennu, TLS) — an environment blocker, not a design problem — and it has a
cheap fix that only the investigator can apply.

**INVESTIGATOR ACTION, ~2 minutes:** open `https://datadryad.org/dataset/doi:10.5061/dryad.j9kd51c9q` in a
browser, download `Farnes_et_al_PLOS_ONE_Dryad.zip` (934 MB), and drop it anywhere readable by the session.
Nothing else in the queue is blocked on it, and it is the highest-value single unblock available for
Challenge A.

---

## Q28 — Challenge B has been asked BETWEEN subjects with a WITHIN-subject marker, and E45 says so

*Brainstormed 2026-07-31 against the full constraint set. Recorded as a ranked idea, **not registered** —
Q14's own sequencing says the ceiling (E63) is measured before any correlation, and jumping that would be
the move `DISCOVERY_LOOP.md` forbids.*

Every Challenge B test in this project has been **between subjects**: E28, E41 and E56 all correlate one
resting-EEG number per subject against that subject's decoding ability. E38's reliability ceiling
(r_sb = 0.2918, cap ρ ≈ 0.5402) is a property of that design.

**But E45 measured five-year test-retest stability on our own estimator and found `lempel_ziv` is a STATE
measure, not a trait.** A state measure is precisely what a between-subject design cannot use and what a
within-subject design wants. **That retrodicts E41's null** — it correlated state-like quantities against a
trait-like label across people — and a finding that retrodicts a standing negative is worth more than one
that adds a positive.

### What Stieger makes possible that eegmmidb never could

**41 subjects have 11 sessions each and 21 have 7** — and the deposit exists to study *learning*, so
session-to-session accuracy variation is largely real rather than noise. That supports a design nobody here
has proposed:

> **Does a subject's session-to-session CHANGE in resting EEG track their session-to-session CHANGE in
> decoding accuracy?**

Its properties are different from, and in places better than, the between-subject question:

* **Immune to every stable between-subject confound** — age, skull thickness, electrode impedance, hair,
  baseline alpha amplitude — because each subject is their own control.
* **Not capped by E38's ceiling**, which bounds how well a subject's *stable* ability can be estimated. This
  asks about change, and the relevant reliability is a different quantity.
* **It is the design a state measure can win**, which is the one this project's own stability work says our
  measures are.

### What it would cost, and the honest caveats

* A second Stieger pass computing features on the **2 s pre-cue baselines** (450 per session × 186 sessions).
  The label pass is already running; the feature pass is a separate and much heavier job.
* **A change score is noisier than a level** — the difference of two noisy measurements. This is not a free
  lunch, and the design must carry its own reliability estimate rather than inherit E63's.
* **`lrtc_alpha` still cannot be tested** (Q14): the deposit is trial-epoched and `lrtc_envelope` now
  refuses rather than shrinking its scales. This would be a test of spectral and connectivity measures.
* Stieger's baseline is a **cued 2 s inter-trial window, not rest** — inherited from Q14 and unchanged.

**Rank: 2, behind E63.** The ceiling comes first because it is cheap, already registered, and because if the
label turns out to be highly reliable then the between-subject design is worth re-running on 62 subjects
before anything more elaborate is built.

---

## Q29 — Challenge A's missing DENOMINATOR is acquired: arousal changed without a drug (ds004902)

**Challenge A closed on VitalDB (Q26) and its unblock was assumed to be a second drug** — Q27's ketamine
set, now behind an anti-scraping wall, or the unsent Turku request. That framing was incomplete.

Challenge A's acceptance condition is *"tracks STATE while carrying little DRUG identity."* Testing it needs
two quantities per measure: **how much it moves for a drug**, and **how much it moves for a state change
that involves no drug at all**. This project has never had the second. Every state cohort it holds — VitalDB,
DOSE-I, ds005620, ds004541, chennu — changes arousal *with* an anaesthetic.

### What was found, verified through the OpenNeuro GraphQL API and S3 mirror

All 447 OpenNeuro EEG datasets were indexed and filtered. **`ds004902` — "A Resting-state EEG Dataset for
Sleep Deprivation", CC0, 8.9 GB:**

* **71 participants × 2 sessions** — normal sleep (NS) vs sleep deprivation (SD), and `SessionOrder` is
  **counterbalanced and recorded per subject**, so session is not confounded with time;
* **both `eyesclosed` and `eyesopen`**, so E44's first-order eye-state effect is a controlled variable
  rather than a lurking one;
* **PVT vigilance and KSS/SSS sleepiness scores per session** in `participants.tsv` — a behavioural and a
  subjective arousal anchor, not just a group label;
* EEGLAB `.set` + `.fdt`, on the open S3 mirror. **No access wall** — unlike Dryad (Q27) or the WBIC
  Chennu host (Q20).

**Smoke-tested and extracting.** The existing `openneuro_multicohort.py` took it with a one-line cohort
entry: 218 matching recordings, 10-channel shared montage, 180 s, 250 Hz, with `(subject, session, file)`
keyed so the two sessions and two tasks stay distinct. It is written to its own table — it is a STATE cohort
and must not contaminate the eyes-closed normative reference.

### The design it enables, and it needs no second drug

Both arms are **within-subject changes**, which is the structurally matched form E53 established:

| arm | contrast | deposit |
|---|---|---|
| drug | awake → anaesthetised, same patients | ds004541 (n=8, 2 sessions) or ds005620 |
| **no drug** | rested → sleep-deprived, same subjects | **ds004902 (n=71, 2 sessions)** |

Per measure, the **ratio of drug-response to drug-free-arousal-response** is Challenge A's acceptance
condition made computable. A measure that responds to both is tracking state; one that responds far more to
the drug arm is a pharmacology detector. The informative object is the *ranking across measures*, not any
absolute — anaesthesia is a much larger state change than one night of deprivation, so every measure will
move more in the drug arm and only the ratio pattern is interpretable.

**Caveats, recorded now rather than discovered later.** The two arms are different deposits, so E53's
cross-deposit floor applies to any magnitude claim; only the within-subject *change* is comparable, and even
then the ranking is the claim rather than the ratio's value. ds004541 is n = 8, which will dominate the
uncertainty. And sleep deprivation is a *mild* arousal change — if no measure moves detectably in the
no-drug arm, the ratio is undefined and rule 53 applies before anything is compared.

---

## Q30 — the transportability audit is the right question and this project cannot yet answer it (E66, 2026-07-31)

E65's accidental discovery — `exponent_gamma` reading **−2.675** on VitalDB and **+29.651** on DOSE-I —
prompted a systematic audit: which of our features survive a change of deposit? E66 registered
R = (IQR of per-deposit medians) / (median within-deposit between-subject IQR), with the mechanistic
hypothesis that R should rank with how close a feature's band sits to the acquisition Nyquist.

**H1 ABSENT: Spearman(R, band_hi / lowest Nyquist) = +0.3669 [−0.3504, +0.8661].** So `exponent_gamma`,
which literally fits 50–90 Hz above a 62.5 Hz Nyquist, is a **special case** rather than the extreme of a
gradient. The anti-alias account does not generalise, and that verdict stands as registered.

### The R table does not measure transportability, and that is my error

G1 admitted exactly four deposits per feature: **chennu** (sedated volunteers), **eegmmidb** (awake adults),
**hbn** (awake **children**, 5–20) and **vitaldb** (**anaesthetised** surgical patients). `lempel_ziv`
medians: hbn 0.228, vitaldb 0.441, eegmmidb 0.623, chennu 0.749. The paediatric value is low because they
are children; the surgical value is low because they are unconscious. **Those differences are the features
working**, and R cannot separate them from transport failure.

The registration named population as a confound, cited rule 50 while doing so, and then computed the
statistic anyway. **Error catalogue rule 54.**

### What a correct audit needs, and why it cannot run today

State- and condition-matched cohorts — eyes-closed resting adults — which means chennu at level 1,
eegmmidb eyes-closed, HBN restricted to its oldest subjects, ds005620 awake, and **vitaldb excluded
entirely** since it holds no awake window at all. That leaves **three** deposits at the full 13-feature
core and about five at the 6-feature intersection, with eye state unlabelled on several of them (E44: eye
state is first-order, so mixing conditions reintroduces a large confound).

**The cohort that would answer this was extracted and then lost.** `multicohort_features.csv` — ds003775,
ds004504, ds004148, ds005385, all eyes-closed resting adults, exactly the matched set required — lived
under `/tmp/eeg_probe` per the "derived subject-level tables are not committed" convention, and went with
a container rollback. That convention exists to keep **credentialed patient data** out of git and it is
right for HEEDB and I-CARE; **applying it to open OpenNeuro deposits cost a table that has to be rebuilt
from scratch.**

**Next step, and it is cheap:** re-extract the four normative cohorts once the current three jobs finish,
and commit that table — it is CC0/open and there is no reason it should be ephemeral. E67 is the
state-matched audit, to be registered against it.

---

## Q31 — Challenge B's ceiling is measured and it is 0.98, not 0.54 (E68, 2026-07-31)

**E41's Challenge B null was never interpretable.** `uce_v1` reached ρ = +0.0853 [−0.1066, +0.2651] against
a minimum detectable 0.272, and E38 had measured eegmmidb's label reliability at r_sb = **0.2918**
[0.1163, 0.4345] — capping any predictor at **0.5402** by attenuation alone. Q14 made the sequencing a
standing rule: measure the ceiling before running the correlation.

**Measured, on 185 sessions from 62 subjects, labels only, no EEG touched:**

| | value | 95 % CI | ceiling |
|---|---|---|---|
| **R1 within-session** (binomial-corrected) | **0.9652** | [0.9568, 0.9706] | **0.9825** |
| R2 across-session (k vs k+1, 122 pairs) | 0.6539 | [0.5282, 0.7361] | 0.8087 |
| **change score** (consecutive-session Δ) | **0.8983** | — | **0.9478** |
| *eegmmidb, for reference (E38)* | *0.2918* | *[0.1163, 0.4345]* | *0.5402* |

No overlap of any kind with eegmmidb. Observed between-session variance 0.018676 against binomial trial
noise 0.000649 — a factor of 29.

### E38's recommendation is confirmed rather than assumed

E38 argued reliability, not n, was the binding constraint, and that **more trials per subject buys more
than more subjects**. 450 trials per session against eegmmidb's 45 in total gives 0.965 against 0.292 — on
**fewer** subjects (62 vs 109). That was a prediction and it held.

### A caveat I wrote into Q28 is retracted by measurement

Q28 warned that "a change score is noisier than a level — this is not a free lunch." **On this deposit it
very nearly is.** The consecutive-session change has variance 0.012706 against 0.001292 of doubled binomial
noise, giving a change-score reliability of **0.8983**. With ~356 scored trials per session, differencing
two near-noiseless measurements costs almost nothing. **Q28's within-subject design is fully viable and its
stated weakness does not apply here.** Mean change is +0.0386 — real learning — and 28.6 % of session
variance is within-subject, which is what a change design has to work with.

### What this does and does not establish

It does **not** show a predictor exists. It establishes that a null measured on this deposit would be a
**real null** rather than an attenuation artefact — which is exactly the condition Q14 required before the
correlation is run, and it is now met.

**Next: the Stieger feature pass over the 2 s pre-cue baselines** (450 per session), then both designs —
between-subject against `relative_alpha_power` as the named incumbent, and Q28's within-subject change
version. The literature (Q-round: PMID 26529439, 37759889, 38986469) says the predictors that work are
connectivity/network/microstate measures, and Stieger's **62 channels** can carry them where every previous
Challenge B deposit could not.

**One thing to capture in that pass that the label pass did not:** `TrialData.triallength`. A binary
hit/miss throws away most of a trial's information; time-to-target is continuous and would raise the
label's precision further at no extra download.

---

## Q33 — the two feature pipelines DISAGREE on identical recordings, and the disagreement is per-feature

*Measured 2026-07-31, rule 20 applied properly: when two scripts compute the same quantity, diff them.*

E53 established a cross-deposit floor and attributed part of it to the pipeline. **This measures the
pipeline difference directly**, by extracting ds005620 through `analysis/openneuro_multicohort.py` and
comparing against the committed `results/ds005620_features.csv` (bsde runner + seed registry) on the
**same eight recordings**.

| feature | multicohort | bsde | relative \|diff\| | rank ρ |
|---|---|---|---|---|
| `whole_head_exponent` | 1.5574 | 1.3481 | **3.1 %** | 0.762 |
| `sef95` / `spectral_edge_95` | 18.96 | 23.25 | 9.0 % | 0.857 |
| `rel_delta` / `relative_delta_power` | 0.6797 | 0.5711 | 19.8 % | 0.905 |
| `rel_alpha` / `relative_alpha_power` | 0.0813 | 0.1121 | 53.2 % | 0.857 |
| **`lempel_ziv`** | **0.0694** | **0.3479** | **83.8 %** | 0.762 |

**Rank correlations are 0.76–0.91, so the pipelines ORDER recordings similarly and their VALUES are not
interchangeable.** `lempel_ziv` differs five-fold. **Name-mapping features across these two pipelines is
invalid for everything except `whole_head_exponent`.**

### What this does and does not do to Challenge A

E74's corrected four-arm table mixes pipelines, so this had to be checked before the finding is quoted:

| arm | pipeline |
|---|---|
| natural N3 sleep (E67) | **bsde** |
| propofol, ds005620 (E67) | **bsde** |
| general anaesthesia, ds004541 (E67) | **bsde** |
| sleep deprivation, ds004902 (E74) | *multicohort* |

**The `lempel_ziv` sign reversal rests on three within-pipeline arms** — natural sleep **−2.281** against
propofol **+1.551** and GA **+0.947**, all bsde-path. The multicohort deprivation arm (−0.324) merely
*agrees in sign* and is corroborative, not load-bearing. **The finding survives.**

And `whole_head_exponent`, whose four-arm consistency makes it Challenge A's current best candidate, is the
feature the two pipelines agree on most closely (3.1 %) — so its cross-pipeline arm is the most trustworthy
one available.

Two further consequences:

* **Any future cross-pipeline comparison must be of within-subject CHANGES, never levels**, and even then
  only for features whose definitions have been diffed. A constant per-subject offset cancels in a paired
  difference; a different binarisation threshold in `lempel_ziv` does not.
* **Extending Challenge A's both-arms feature set requires re-extracting ds004902 through the bsde path**,
  not name-mapping. The S3 adapter is EDF-only and ds004902 is EEGLAB `.set` + `.fdt`, so that needs a
  loader — which is the concrete next task for this challenge.

---

## Q34 — the BIS-like index does NOT track a clinician's judgement, and Q22's licence is withdrawn (E65)

Q22 built a computable BIS-like index, E58/E60/E62 measured it against device BIS at median |err| **3.47**
in [40,60), and the deliverable was: use it on monitor-free deposits inside [20,60) with ±3.47 attached.
**That licence rested entirely on agreement with device BIS, measured on the recordings the index was
fitted to.** E65 is the first external test, against a human rather than a machine.

| measure, same 39 DOSE-I recordings | FULL arm | SAFE arm |
|---|---|---|
| **our BIS-like index** | **+0.0375** [−0.1501, +0.2893] | **+0.0417** [−0.1756, +0.1424] |
| DOSE-I's own **PE31** | +0.3974 [+0.3098, +0.4636] | **+0.4813** [+0.4093, +0.6332] |
| DOSE-I's own SEF95 | −0.0197 [−0.1155, +0.1109] | +0.2507 [+0.0762, +0.3833] |

**Depth information is present in this EEG and is recoverable** — permutation entropy, the incumbent E33
named from Ostertag et al., reaches **+0.48** on the same windows. Our index reaches **+0.04**.

### It is not a flat-model artefact, and not transport drift

Predictions vary on DOSE-I at sd 12.02 (FULL) and 5.04 (SAFE) against sd 5.48 on the VitalDB fit set. The
model moves; it moves independently of the clinician. And the SAFE arm drops all seven drifting features
(`bis_bsr` and `bis_quazi` at infinite shift, `bis_sfs` 1.730, `multiscale_entropy_slope` 1.574,
`whole_head_exponent` 1.288, `lempel_ziv` 1.203, `exponent_high` 1.122) — **the answer does not change.**

One diagnostic is worth keeping: the SAFE model's entire predicted range (30.8–50.1) sits inside the
licensed band, so 100 % of windows "pass" the refusal rule. **A model whose output cannot leave the band it
was fitted in is not being restrained by the rule; it has regressed to its training mean.**

### The reading, and the caveat that cannot be settled here

The parsimonious conclusion is that **the index learned to reproduce the BIS algorithm on one device and
population, not anaesthetic depth.** Reproducing a proprietary index is not the same as measuring what the
index claims to measure.

The caveat: the index was fitted to predict *device BIS*, and MOAA/S is a different target. If BIS itself
tracked MOAA/S poorly, a BIS-faithful index would too — and DOSE-I has no BIS while VitalDB has no MOAA/S,
so the two references cannot be compared directly with data in hand. Published sedation work puts
BIS-vs-MOAA/S in the moderate-to-strong range, which makes +0.04 hard to explain that way, but this
experiment does not measure it.

**Either reading has the same practical consequence, so the licence goes:** the index cannot serve as a
depth comparator on monitor-free deposits, which was Q22's entire purpose. `BIS_FAITHFUL_OR_BRAIN_FAITHFUL.md`
asked whether the comparator should be BIS-faithful or brain-faithful and chose BIS-faithful-where-BIS-
measures-brain. **E65 says that choice bought a measure of BIS, not of brain.**

### What survives, and what to do instead

* The **per-band fidelity work (E58/E60/E62) stands** — it accurately describes agreement with device BIS,
  which is what it measured.
* **PE31 is the comparator to use.** It is published, computable, shipped by the deposit, and it tracks a
  clinician at +0.48 where our fitted index tracks at +0.04. E26/E34/E37 scoped themselves "ahead of SEF95";
  the honest incumbent is permutation entropy, and it is stronger than SEF95 here too.

---

## Q35 — the composite failed, its INGREDIENTS did not, and Q34's recommendation is amended

*EXPLORATORY. A 29-feature scan run post-hoc on the data E65 had already used. It is recorded because it
changes what E65 means, and a registered replication is owed before any of it is quoted as a result.*

E65 found the fitted BIS-like index reaches ρ **+0.04** against a clinician's MOAA/S. The natural reading —
*our features carry no depth information* — is **wrong**. Scanning each feature individually on the same
39 recordings:

| feature | median ρ vs MOAA/S |
|---|---|
| **`bis_rbr`** | **+0.5258** |
| *DOSE-I's own PE31* | *+0.4813* |
| `relative_alpha_power` | −0.4270 |
| `whole_head_exponent` | −0.4218 |
| `exponent_high` | −0.3984 |
| `emg_index` | +0.3877 |
| *DOSE-I's own SEF95* | *+0.2507* |

**Nine of our features exceed |ρ| = 0.3 against a human's judgement, and the best of them beats both
published measures the deposit ships.** So the diagnosis is sharper than E65 could state: **fitting to
device BIS destroyed information that the ingredients individually carry.** The ridge weighted features by
their VitalDB-BIS relationship, and those weights are wrong for depth — wrong enough to cancel.

### The muscle check, and why it does not explain it

Three of the top eight are muscle proxies and `bis_rbr`'s numerator band (30–47 Hz) is where surface EMG
lives, so this was the obvious objection. Partialling each scalp proxy out:

| | raw | \| `emg_index` | \| `emg_kurtosis` | \| `emg_beta_gamma_fraction` |
|---|---|---|---|---|
| `bis_rbr` | 0.5258 | 0.3153 | 0.4364 | 0.3561 |
| PE31 | 0.4813 | 0.3310 | 0.4168 | 0.2819 |

**`bis_rbr` and PE31 attenuate by the same proportion**, so the edge is not a muscle artefact. And the
adjustment is an over-adjustment in the first place: muscle tone is *part of* the sedation response, not a
pre-exposure confound, so conditioning on it removes real signal (rule 13).

### What this changes

* **Q34's "PE31 is the comparator to use" is amended.** `bis_rbr` — implemented here from Rampil's published
  description — matches or beats it on this deposit under every adjustment tried. Neither should be adopted
  on a post-hoc scan.
* **E65's verdict stands and its interpretation narrows.** The composite does not track a clinician; that is
  a fact about the *fit*, not about the feature set.
* **The lesson for the deliverable:** a comparator should be fitted to the reference it will be judged
  against, or not fitted at all. Fitting to a proprietary index and hoping depth comes along did not work.

### Owed before this is used

A registered test on a deposit or a partition not used here, with `bis_rbr` and PE31 pre-declared, and the
29-feature multiplicity handled rather than noted. DOSE-I ships no EMG channel, so the muscle question
cannot be settled on it — Sleep-EDFx can (E70's submental channel), and `bis_rbr` was never computed there.

---

## Q36 — our permutation entropy is a good but not faithful PE31, and the shortfall is where the claim lives

*Rule-23 validation, run because Q34 named PE31 the Challenge C comparator and Q35 amended that to `bis_rbr`.
Neither is usable off DOSE-I unless we can compute it ourselves.*

`bsde/scripts/extract_dosei_pe.py` computed this repo's `permutation_entropy(order=3, delay=1)` on **10,927
windows across 39 DOSE-I recordings**, in a 30 s window ENDING at each pEEG timestamp (causal, no lag search),
beside the deposit's own `PE31` column. Verified against the raw CSV rather than the run log:

| | median within-recording ρ | IQR |
|---|---|---|
| **agreement** ρ(ours, PE31) | **+0.7239** | [+0.2885, +0.8183] |
| placebo: our series circularly shifted within recording | **−0.1238** | [−0.3854, +0.1997] |
| ours vs the deposit's clinician-rated MOAA/S | **+0.3545** | [+0.1816, +0.6581] |
| **PE31** vs the same MOAA/S | **+0.4944** | [+0.3444, +0.6532] |

**The parameters are nominally identical.** The deposit's `pEEG_parameter_description.txt` says of the column
it names `PE31`: *"Permutation Entropy (PE) according to Olofsen et al. (2008), band: 0.5-45 Hz, n=3, tau=1,
tie=0.5 uV"*. Our call is order 3, delay 1. The column-name/description alignment was checked two ways —
description column 31 is n=3 **tau=2** and the CSV's next column is named `PE32`, so the mapping is not
off by one and we are compared against the matching parameterisation.

**So the finding is a shortfall, not a validation.** Agreement is strong and the placebo is flat, which
establishes that we compute *a* permutation entropy correctly. But on the quantity Challenge C actually needs
— tracking a human's judgement — ours reaches +0.3545 where theirs reaches +0.4944 **on the same recordings,
the same windows and the same label**. A 0.14 gap in ρ is not rounding.

**The deposit names exactly two steps we do not perform: the 0.5–45 Hz band limit and the 0.5 µV tie
threshold.** `permutation_entropy` now takes `tie_threshold` (default 0.0, leaving the existing code path
bit-identical, with 10 tests that each construct the input that must make it behave one way), and **E76 is
registered** to ask whether those two steps close the gap — with an arbitrary-wrong-band placebo (0.5–20 Hz)
fixed before any number existed, because a low-pass that helps regardless of which low-pass it is would
show band sensitivity rather than mis-specification.

**Why it is worth the pass.** Q34's "PE31 is the comparator to use" is only usable on deposits that ship
PE31 — i.e. this one. If the declared recipe reproduces it, the comparator becomes portable; if it does not,
something undeclared separates the two implementations and Q34's recommendation is deposit-bound, which is a
constraint on Challenge C rather than an inconvenience.

**What this does NOT say.** Nothing here ranks permutation entropy against `bis_rbr`, and nothing licenses
either as a measure of consciousness. Q35's owed registered replication is still owed.

---

## Q37 — E76: the declared preprocessing explains the gap, and Challenge C's comparator becomes portable

*Registered before its data existed (E76, ledger SHA `c97227e6`); both co-primaries PASS.*

Q36 left our permutation entropy agreeing with DOSE-I's shipped `PE31` at ρ **+0.7239** while tracking the
deposit's clinician-rated MOAA/S at **+0.3545** against `PE31`'s **+0.4944**, at nominally identical n=3,
τ=1. The deposit declares two steps we did not perform. **Both were applied and the gap closes.**

On 43 recordings and 12,170 windows:

| arm | median ρ vs PE31 | median ρ vs MOAA/S |
|---|---|---|
| `pe_raw` (as-is) | +0.7241 | +0.3638 |
| `pe_band` (0.5–45 Hz) | +0.8246 | +0.5264 |
| `pe_tie` (0.5 µV ties) | +0.7270 | +0.3700 |
| **`pe_declared`** (both) | **+0.8288** | **+0.5304** |
| `pe_placebo20` (wrong band, 0.5–20 Hz) | +0.4267 | +0.2563 |
| *the deposit's own `PE31`* | — | *+0.4944* |

    P1 agreement   D = +0.2457 [+0.1468, +0.3601]   placebo -0.1466   contrast +0.3923 [+0.3385, +0.4469]
    P2 clinician   D = +0.1609 [+0.0764, +0.2613]   placebo -0.1097   contrast +0.2706 [+0.1822, +0.3646]

0 of 20,000 resamples on the wrong side in either, identical verdicts at three seeds.

**The placebo does not merely fail to help — it hurts.** An arbitrary 0.5–20 Hz band makes agreement *worse*
than doing nothing. So the gain is specific to the band the deposit declares, not to low-passing in general,
which is the only reading that supports "our implementation was mis-specified" over "permutation entropy is
band-sensitive".

**The decomposition is one-sided and it is the useful part** (descriptive, not gated): the band does
essentially all of it — **+0.2383 of P1's +0.2457** and **+0.1620 of P2's +0.1609** — while the 0.5 µV tie
threshold contributes **+0.0234 [+0.0089, +0.0414]** on agreement and **+0.0077 [−0.0021, +0.0188]** on
MOAA/S, the second spanning zero. The tie rule was *active* (16–17 % of embedded windows carry a tied pair,
gate G2), so that is a measured near-null rather than an inapplicable arm. **If you implement one of the two
steps, implement the band.**

**G4 is the machinery result worth keeping.** `pe_raw` reproduced the earlier pass's `mine_pe` on all
**10,927 shared rows with max |diff| = 0** — exact, through a completely rewritten vectorised inner loop.

### What this changes for Challenge C

Q34 concluded "PE31 is the comparator to use", which bound Challenge C to deposits that ship a PE31 column —
i.e. DOSE-I alone. **That constraint is lifted.** With the declared recipe our own PE reaches +0.5304 against
MOAA/S where the shipped column reaches +0.4944. *That comparison is descriptive: no interval comparison was
performed and no superiority is claimed.* What is claimed is portability.

### The first evaluation refused, and the record of it is kept

At 26 recordings the coverage gate G5 (registered floor 30) refused and printed `GATE FAILED`, correctly.
The shortfall was the launch argument, not the design — `--n-recordings 40` stops at `10-060` and 14 of those
40 fail the shared non-uniform-time-axis rule. `results/e76_first_pass_note.md` records the full descriptive
table that was visible before the extraction was extended, so a reader can judge that decision rather than
take it on trust.

---

## Q38 — E75: the aggregate is a NULL, and the verdict code was what hid it

*E75 first printed `SPLIT — AGREE [...]; REVERSE [...]`, described in its own registration as "the
informative outcome" and "Challenge A's candidate list". **That verdict is withdrawn.***

E75's registered branch (c) was "NOT INFORMATIVE — the label-permutation placebo reproduces the agreement
rate", coded as `abs(real - 0.5) <= abs(placebo_mean - 0.5)`. **It could not fire for any data.** The placebo
mean is an average over 300 draws and sits at ~0.500 by construction; the real rate is a fraction over an
**odd** number of testable features and can never equal 0.500 either. Compared against the placebo's
*distribution* — which is what the registered sentence actually means — **0.487 of draws reach the observed
0.571 or better**, and 4 of 7 is precisely the median of a Binomial(7, 0.5). Fifth occurrence of rule 37's
family; now in `CLAUDE.md`.

**Per-feature signs stand as descriptive** (each is determined by its own G1 interval), and they reproduce
E74 exactly:

| same sign, drug and no-drug | reversing |
|---|---|
| `critical_slowing_ar1` +3.256 / +0.515 | `exponent_low` +3.157 / −1.238 |
| `emg_beta_gamma_fraction` −1.906 / −0.900 | `lempel_ziv` −2.281 / +1.505 *(reverses on drug-B too)* |
| `spectral_edge_95` −2.868 / −0.772 | `multiscale_entropy_slope` +3.612 / −1.372 |
| `whole_head_exponent` +4.008 / +1.120 *(agrees on drug-B too)* | |

**What must not be said:** that the left column is a class of measures. The set carries no more structure
than chance, and the presence of `emg_beta_gamma_fraction` — a muscle measure — in it is what "sign agreement
is necessary, not sufficient" looks like when it bites.

**Two machinery facts the design was not built to find and which are not softened.** `uce_v1`, this
project's flagship candidate, is **empty in all 710 rows** of the Sleep-EDFx five-stage table and could not
enter the no-drug arm at all. `exponent_high` — the feature E69, E70 and E77 all concern — **failed the
depth-monotonicity gate**, so its cross-arm sign is uninterpretable.

---

## Q39 — the flagship candidate is uncomputable on the wedge deposit, and one third of that is a parsing gap

*Found while diagnosing why `uce_v1` was blank in E75's no-drug arm. Surveyed across every result table in
`bsde/results/` that carries a `uce_v1` column.*

| deposit | finite `uce_v1` | why |
|---|---|---|
| ds005620, ds004541, ds007554, Chennu, eegmmidb, figshare | all rows | 10–20 names, both regions present |
| **VitalDB** (`vitaldb_grid`, `vitaldb_fine`, `vitaldb_challenge_a`) | **0 of 11,000+** | **1 channel.** A BIS strip has no posterior electrode |
| **Sleep-EDFx** (five-stage, multiwindow, staged) | **0 of 2,200+** | **2 bipolar derivations**, `EEG Fpz-Cz` / `EEG Pz-Oz`, matched by neither region set |
| **HBN** (`hbn_r1_resting`) | **0 of 272** | **125–128 channels**, EGI `E<n>` naming, matched by neither region set |

**These are three different problems and only one is a bug.**

1. **VitalDB is a real montage limit and is not fixable.** UCE v1 is a frontal-versus-posterior contrast and
   VitalDB's EEG is one channel. `regional_exponents` returns NaN rather than substituting, which its own
   docstring says is deliberate — *"silently substituting would make UCE v1 computable on montages that
   cannot support it"*. It is right. **But the consequence is that the project's flagship candidate cannot
   be computed on the deposit named as its commercial wedge**, and every VitalDB result to date has
   therefore been about other measures. That is a scope fact, not a defect, and it belongs in
   `MASTER_PLAN.md` rather than in a footnote.
2. **Sleep-EDFx is a judgement, not a parse.** `Fpz-Cz` spans frontal to central and `Pz-Oz` parietal to
   occipital; calling the first "frontal" and the second "posterior" is an assignment someone has to make
   and defend, and a bipolar derivation's aperiodic exponent is not the same quantity as a monopolar
   channel's. Left NaN, deliberately. **Consequence: the only drug-free arousal deposit this project has
   structurally excludes UCE**, which is why E75's no-drug arm could not test it.
3. **HBN is a genuine parsing gap and 272 large-montage recordings are being dropped for it.** `E22`, `E70`
   and the rest are EGI net positions with a documented 10–20 correspondence; `group_indices` does exact
   matching against a 10–20 name set and matches none of them. This is rule 5 — empty was read as absence
   without checking the filter could match anything.

### What to do, and what NOT to do

**Do not hardcode an EGI-to-10-20 table from memory.** Rules 25 and 39 exist because this project has had a
citation and a file manifest fabricated by a summariser; electrode numbers are exactly the kind of specific,
plausible, checkable detail that gets invented. The fix requires the mapping pulled from the net
manufacturer's or the deposit's own documentation and parsed, not recalled.

**Do not change the frozen equation.** `uce_v1` is `version="1.0-frozen"`. Widening which montages are
*admissible* is a separate change from what the measure *computes*, and only the first is on the table.

Registered as an open item rather than done here, because it needs a verified source and because it changes
what a frozen candidate can be evaluated on.

### Priority, on reflection, is the opposite of the list order

**HBN is the fixable one and the least worth fixing.** It is resting state in a developmental cohort with no
arousal manipulation, so unlocking `uce_v1` there advances none of the three challenges; rule 54 also warns
against pooling it with adult deposits. A verified fix is available in principle — MNE ships both
`GSN-HydroCel-128` and `standard_1020` with 3D coordinates, so the mapping can be *derived geometrically*
(nearest standard position within a tolerance) rather than recalled, which is what rules 25 and 39 require.
Worth doing when something needs HBN; not worth doing now.

**Sleep-EDFx is the one that costs something, and it has a concrete option.** The exponent of a bipolar
derivation is a perfectly real quantity — it is just not the same quantity as a monopolar channel's, so it
must never be pooled with, or compared against, monopolar `uce_v1` values. But E75's question needs only the
SIGN of each arm's own within-subject effect, with each arm standardised inside itself, and a bipolar-basis
UCE is admissible for exactly that. **The proposal is a separately named candidate `uce_v1_bipolar`,
registered on its own, never written into a column called `uce_v1`** — so that no table can silently mix two
measurement bases. That it would not change E75's verdict (already NOT INFORMATIVE on its aggregate) is a
reason to register it properly rather than bolt it on.
