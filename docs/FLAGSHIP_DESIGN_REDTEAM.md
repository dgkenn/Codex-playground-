# Pre-mortem hostile review — frozen-CBraMod attention/MIL head, abnormal-EEG, S0001→I0002

**Role:** Reviewer 2, top-tier venue (Nature Medicine / Lancet Digital Health / JAMA). This is a DESIGN
review before data are touched, per the hostile-review gate in `docs/RESEARCH_MACHINE.md`. Grounded in
`docs/LESSONS.md`, `docs/HEEDB_UNLOCK.md`, `docs/HEEDB_FAILURE_ANALYSIS.md`.

**Proposed design under review:** Frozen CBraMod embeddings (per-window, µV-scaled, 24 windows/recording)
→ trained attention/MIL head → predict abnormal-vs-normal EEG (report label) → train S0001, test I0002
(HEEDB), ~450 patients/site, balanced, frozen encoder, CPU-only.

**Verdict up front:** this design, as stated, does not survive review. It will draw a desk-reject or a
brutal R&R on novelty (Lens 3) and site-confound (Lens 2) grounds even if the numbers look good. Sections
below give the attack and the concrete fix for each. Section 7 gives the single recommended primary outcome
+ validation design that survives.

---

## 1. CRITICAL — Site = hospital confound / shortcut learning (Lens: causal/confounding)

**The attack.** Train S0001, test I0002 is a single train-site/single-test-site split with n≈450/site.
CBraMod embeddings are known (this repo's own diagnostic, `HEEDB_FAILURE_ANALYSIS.md`) to be dominated by
gross signal characteristics — PC1 = 67% variance, correlated with amplitude (r=-0.51) in the *mean-pooled*
case. An attention/MIL head over per-window tokens removes the mean-pool bottleneck but does **not** remove
the underlying scanner/montage/amplifier signature that CBraMod's tokens encode: differences in electrode
impedance, reference scheme, amplifier gain/filter characteristics, and recording software all imprint on
raw EEG voltage/frequency content in ways a foundation model — frozen or not — will happily use as a
shortcut, *especially* if "abnormal" prevalence, physician reading style, or hardware correlates with site
(which it will: S0001 vs I0002 are different hospitals with different EEG techs, different montages, and
plausibly different indication mix for ordering EEG). A reviewer's very first question will be: "You have
one train hospital and one test hospital. How do you know the model isn't just learning 'this is I0002's
amplifier,' which happens to correlate with I0002's abnormal-EEG base rate or reading conventions?" This is
not a hypothetical — this repo already built `analysis/site_probe.py` specifically because a Route-A
correction can silently fail and a hospital ends up encoded in the "cleaned" embedding. Reviewers who know
the EEG domain-shift literature (multi-site EEG harmonization work, e.g. ComBat-for-EEG, cross-scanner MRI
harmonization precedent) will demand exactly this control, and if you don't preempt it, it becomes the
whole review.

**Why the current design fails to rule it out.** Two sites, one direction (S0001→I0002), no reverse
direction reported, no site-invariance diagnostic, no montage/hardware audit, no within-site negative
control. Even a perfect cross-site AUC is not interpretable as "abnormality" versus "site fingerprint plus
whatever correlates with site" without these controls.

**The fix (concrete, buildable now with existing repo code):**
1. **Run `site_probe.py` on the *raw* per-window embeddings before any correction**, treating
   {S0001, I0002} as the label. Report this AUC in the paper as a domain-shift audit, not just an internal
   gate. If it's high (it likely will be, matching the amplitude-dominance finding), that is itself the
   headline confound to disclose and correct.
2. **Apply Route A site-correction (`correct_sites.py`, ComBat-style) to the per-window tokens** (not just
   at the pooled-embedding stage) before the MIL head, fit on train-site statistics only and applied to the
   held-out site via `transform_new_site` — never fit correction using test-site labels.
3. **Re-run `site_probe.py` after correction** and require AUC ≤ chance tolerance (repo default 0.58) as a
   **published gate**, exactly as Phase-1 phenotype discovery already requires. Report pass/fail explicitly
   in the methods, not just internally.
4. **Bidirectional cross-site test**, not one direction: train S0001→test I0002 **and** train I0002→test
   S0001. If only one direction transports, that is evidence of a site artifact (e.g., S0001 has more data
   / cleaner labels) rather than a biological signal, and must be reported, not cherry-picked.
5. **Add a third, fully independent site as a tie-breaker** if HEEDB has ≥3 usable sites (the catalog lists
   S0001, S0002, I0001–I0009). Two-site ping-pong (A→B, B→A) is still consistent with "the model learns
   site X's signature and site Y's differs the same way abnormality does by chance." A third site
   (train on S0001, validate hyperparameters/threshold on I0002, report primary test AUC on a third,
   never-touched site, e.g. S0002 or I0001) is the design that a hostile reviewer cannot wave away — it is
   also directly consistent with this repo's existing hospital-split confirmatory design in the
   preregistration.
6. **Montage/hardware audit as a table 1 covariate**: report per-site channel montage (10-20 subset used),
   sampling rate, amplifier/manufacturer if in HEEDB metadata, and recording duration distribution. If these
   differ materially by site, that is exactly the pathway of a shortcut and must be explicitly discussed
   even after passing the site_probe gate (a gate can fail to catch a shortcut that correlates with, but
   isn't identical to, linear site separability).
7. **Negative control task**: predict a label known to be clinically unrelated to EEG pathology but
   plausibly site-correlated (e.g., patient sex, or day-of-week of recording, if available) from the
   corrected embeddings. If these remain unpredictable, this strengthens the claim that correction removed
   site machinery rather than clinical signal.

This is the single most likely cause of a rejection if skipped, and it is also the cheapest to build --
`site_probe.py` and `correct_sites.py` already exist in this repo.

---

## 2. CRITICAL — Novelty: "abnormal EEG" is solved on TUAB (~0.90); cross-site alone is not a paper

**The attack.** Abnormal-vs-normal EEG classification is a well-trodden benchmark (TUAB), with published
CBraMod / LaBraM / EEGPT / BIOT numbers in the 0.87-0.92 range, largely with encoder fine-tuning. A
reviewer who works in this space will immediately ask: "what is new here beyond 'we ran an existing
benchmark task on a different, smaller, private dataset with a weaker (frozen) model and got worse
numbers'?" Cross-site generalization is a real and underexplored question, but demonstrating it on the
*existing, solved* task risks being read as a methods/negative-result footnote rather than a flagship
contribution — worse, if the cross-site AUC lands south of TUAB's frozen or fine-tuned baselines (plausible
given `HEEDB_FAILURE_ANALYSIS.md`'s frozen-mean-pool ceiling finding, ~0.5-0.62 in this repo's own pilots),
the paper reads as "we reproduced a known task worse and on a smaller n." The repo's own `LESSONS.md` /
`RESEARCH_MACHINE.md` novelty discipline flags this exact risk: "avoid already-named indices / solved
benchmarks; the novel contribution must be a construct with no established literature." Abnormal/normal EEG
classification is precisely such an already-solved construct.

**Why "first cross-site HEEDB validation" is necessary but not sufficient.** "Nobody has cross-site
validated an EEG foundation model on HEEDB for X" is true and worth a sentence, but a hostile reviewer will
respond: "then do it on an outcome that isn't already solved elsewhere, so the cross-site result is the
*headline*, not a caveat on a solved task." Doing the *easy*, solved task cross-site invites exactly the
comparison ("TUAB gets 0.90 fine-tuned; you get 0.6-0.7 frozen cross-site — so frozen + cross-site is just
worse, not new").

**The fix.**
- **Do not make abnormal-vs-normal the primary/headline outcome for a flagship claim.** Use it as a
  **calibration / sanity-check outcome** (Aim 1: does the pipeline recover a known, easy signal at all,
  cross-site, after site correction?) — this is exactly the role it already plays in `HEEDB_UNLOCK.md`'s
  diagnostic ladder ("if abnormal-EEG transports, the pipeline is sound"). Publish it as a **methods
  validation figure**, not the primary endpoint.
- **Make the primary, publication-defining outcome something with no existing foundation-model literature**
  — per this repo's own gap analysis (`HEEDB_UNLOCK.md`: "no EEG foundation model has been applied to
  clinical/neuro outcome prediction with external validation anywhere as of 2026"). Candidates already
  identified in this repo: cognitive/behavioral-syndrome ICD (encephalopathy/delirium spectrum) or
  mortality via DateOfDeath — both reflect diffuse background severity, which is exactly what a
  window-attention MIL head over a frozen encoder is best positioned to detect (see Section 4), and neither
  maps to a named benchmark or a solved literature. See Section 7 for the concrete recommendation.
- If reviewers still want an abnormal/normal number for calibration, report it explicitly framed as
  "consistent with, not exceeding, published fine-tuned TUAB benchmarks; frozen + cross-site" and use it to
  bound expectations for the primary outcome, not compete with the benchmark literature.

---

## 3. CRITICAL — Label validity: "abnormal EEG" is a noisy, heterogeneous, single-reader label

**The attack.** The report-level normal/abnormal label pools an enormous range of pathology (focal slowing,
diffuse slowing, epileptiform discharges, asymmetry, burst-suppression, artifact-heavy-but-technically-
abnormal reads, etc.) into one binary bit, assigned by one clinical reader per report with no stated
inter-rater reliability. A model trained to predict this is, at best, learning to reproduce **one
neurologist's gestalt impression**, confounded by that reader's threshold, site-specific reporting culture
(some sites over-call "mild diffuse slowing" as abnormal; others don't), and indication-driven referral
patterns (an EEG ordered for "rule out seizure" versus "encephalopathy work-up" changes the prior and the
reader's threshold). A reviewer will ask: "abnormal compared to what ground truth? If two neurologists
read the same EEG, do they agree with each other as often as your model agrees with reader 1?" Without an
inter-rater benchmark, an AUC of 0.75 against a single reader could just mean "the model learned reader 1's
idiosyncrasies," which is clinically uninteresting and non-generalizable to reader 2's hospital.

**The fix.**
1. **Report inter-rater/inter-site label-prevalence heterogeneity as a quantified confound**, even without
   dual-reader data: show abnormal-EEG base rate by site and by ordering indication (if available in HEEDB
   metadata) to demonstrate (or bound) reader/site labeling drift. If HEEDB has any dual-annotated subset or
   an addenda/reads-over-time structure, use it for a kappa estimate; if not, state the absence explicitly
   as a limitation up front, not something a reviewer discovers.
2. **Prefer a finding-specific label over the pooled binary** where feasible — HEEDB's
   `<SITE>_EEG_reports_findings.csv` (per `HEEDB_UNLOCK.md`) already carries structured finding flags
   (spikes/spindles/etc.), not just normal/abnormal. A specific finding (e.g., epileptiform
   discharges present/absent, or diffuse slowing present/absent) is a narrower, more physiologically
   grounded, more defensible target than the omnibus "abnormal" bit, and is less reader-gestalt-dependent
   because it maps to a describable EEG feature.
3. **Best fix: replace the label with a hard, non-report-derived clinical outcome** entirely (mortality,
   ICD-coded cognitive/behavioral syndrome) — this simultaneously fixes the label-validity problem (an
   ICD/death outcome doesn't depend on one neurologist's gestalt "abnormal" call) and the novelty problem
   (Section 2). This is the direction Section 7 recommends.
4. If abnormal/normal is retained as a calibration aim, explicitly caveat it in the paper as "reproduces a
   single-reader label, not an independent ground truth" — do not oversell it as a "diagnostic" result.

---

## 4. MODERATE-CRITICAL — Frozen-head ceiling: will reviewers demand fine-tuning, and what's the honest AUC

**The attack.** This repo's own failure analysis is damning and public (to the review team, it will be
found if a reviewer replicates or if you cite your own preprint/repo): frozen mean-pooled CBraMod
embeddings are low-rank, amplitude-dominated (PC1 = 67% variance), OOF AUC ~0.5 despite in-sample AUC ~1.0,
flat across PCA dims/regularization — i.e., **not fixable by a better classifier head over mean-pooled
embeddings.** An attention/MIL head over per-window (not mean-pooled) tokens is the correct mitigation the
repo already identified, but it is *unproven* at the token level — the diagnostic was run on pooled
embeddings only. A reviewer who reads the CBraMod/LaBraM papers will know encoder fine-tuning is where most
of the published AUC gain comes from and will ask directly: "did you try fine-tuning, even partial
(last-block unfreeze, LoRA-style adapters), and if not, why should we believe frozen + MIL closes enough of
the gap to be worth publishing?" A purely frozen result that lands at, say, AUC 0.65-0.70 cross-site,
compared to 0.90 fine-tuned TUAB, invites "incremental / not ready" framing.

**The fix.**
1. **Validate the MIL-head fix at the token level before committing to it as the whole method.** Run the
   same diagnostic ladder from `HEEDB_FAILURE_ANALYSIS.md` (in-sample vs OOF gap, PCA-dim sweep,
   regularization sweep, PC1 variance share) on **per-window token features feeding the attention head**,
   not just the final pooled output. If the attention head's *learned* pooling still collapses to a
   near-linear function of one or two dominant axes (check attention-weight entropy / effective rank of the
   post-attention representation), the MIL head has not actually escaped the ceiling — say so before
   claiming it as the fix.
2. **Pre-register the honest expectation and frame accordingly**: state explicitly, ahead of running, that
   frozen + MIL is expected to land below fine-tuned literature benchmarks (cite CBraMod/LaBraM/EEGPT
   numbers), and that the paper's contribution is *feasibility + cross-site generalization under a
   CPU-only, frozen-encoder constraint*, not SOTA accuracy. This reframes "lower AUC than TUAB fine-tuned"
   from a weakness into an explicitly scoped, honest claim.
3. **Add a cheap, CPU-feasible partial-adaptation ablation as a robustness arm, not the headline**: a linear
   or shallow-MLP probe on frozen tokens vs. the attention/MIL head vs. (if any GPU budget exists at all,
   even briefly) a last-layer/adapter fine-tune, to show the *marginal* value of attention over pooling and
   bound how much is left on the table from fine-tuning. Even a small, clearly-labeled "upper bound" arm
   with n too small to be a claim, run on a borrowed GPU-hour, defuses "did you even try" from reviewers.
4. **Do not claim SOTA.** Position the contribution as: *first demonstration that a frozen, CPU-trainable
   MIL head over an EEG foundation model transports a clinical signal across hospitals* — novelty is in
   the cross-site transportability + the practical (no-GPU-required) training recipe, not raw AUC.

---

## 5. MODERATE — Selection bias, power, p>>n on the head, cross-site CI, multiplicity

**The attack.**
- **Small-EDF / recording-length selection.** If short or corrupt EDFs are silently dropped (the pipeline
  windows to 24×~30s, ~12 min), whatever criterion selects "usable" recordings may itself correlate with
  clinical severity (e.g., very sick/unstable patients get shorter or interrupted routine EEGs; long-term
  monitoring cases get excluded or truncated differently). This is a selection-into-sample bias a reviewer
  will flag under STARD/TRIPOD-AI reporting requirements for diagnostic-model papers.
- **n≈450/site is underpowered for a stable cross-site CI on AUC**, especially once split for
  hyperparameter selection vs. final test. A cross-site AUC of, say, 0.68 on n=450 balanced has a
  bootstrap CI plausibly spanning ~0.62-0.74 — reviewers will require the CI be reported and will read a
  point estimate without CI as an attempt to hide instability. Given this repo's n=89 pilot already showed
  in-sample/OOF AUC gaps of 1.0 vs 0.5, n=450 is better but still modest for a MIL head with many parameters
  relative to n (p>>n risk on the head itself, not just the embedding).
- **p>>n on the head.** An attention/MIL head over 24 windows × per-window embedding dim (CBraMod pooled
  dim ~400, or larger if full tokens are kept) has a nontrivial parameter count trained on ~450 site-S0001
  recordings. Overfitting the head to S0001 particulars (not just site artifacts but genuine small-sample
  idiosyncrasy) is a live risk that must be shown, not assumed away, via the in-sample vs. cross-validated
  OOF gap — exactly the diagnostic already used in `HEEDB_FAILURE_ANALYSIS.md`.
- **Multiplicity.** If the team runs several outcome candidates (abnormal-EEG, encephalopathy, mortality,
  seizure-disorder — all already tried per `HEEDB_UNLOCK.md`'s pilot log) and reports the best-performing
  one as "the" result, that is undisclosed multiple-comparisons / outcome-switching. The repo's own
  pilot history (seizure-disorder AUC 0.41-0.47 null → abnormal-EEG tried next) is exactly the pattern a
  hostile reviewer would flag as post-hoc outcome selection if not pre-registered.

**The fix.**
1. **Pre-register the primary outcome, the train/hyperparameter/test site assignment, and the model
   architecture before looking at I0002 test performance** — this repo already has a preregistration
   protocol and freeze/hash-verification machinery (`phase2/freeze.py`, `guards/heldout_guard.py`); route
   this study through the same discipline: freeze the head architecture + hyperparameters + site-correction
   transform on S0001 only, hash them, then unlock I0002 exactly once for a single confirmatory test — do
   not iterate against the I0002 result.
2. **Report a bootstrap or DeLong CI on every cross-site AUC**, not point estimates.
3. **Report the in-sample vs. OOF (within S0001, cross-validated) AUC gap for the head** before ever
   touching I0002, using the same diagnostic ladder as the failure analysis, as a pre-registered go/no-go
   gate: if the S0001-internal OOF/in-sample gap is large (memorization), do not proceed to the confirmatory
   I0002 test — fix the head (regularization, fewer windows, simpler pooling) first.
4. **Explicitly report and audit the EDF-inclusion/exclusion pipeline** (how many recordings dropped, why,
   and whether drop rate / reasons differ by site or by outcome label) as a CONSORT/TRIPOD-AI-style flow
   diagram — required by most top-tier venues for a diagnostic-prediction paper now.
5. **If multiple outcomes are explored (as they already have been), report all of them** (including the
   nulls already logged in `HEEDB_UNLOCK.md`) with a clearly pre-registered primary and the rest as
   secondary/exploratory, per this repo's own honesty guardrail ("report nulls and confounds faithfully").

---

## 6. MODERATE — The clinical "so what": publishable at top tier vs. a methods note

**The attack.** Even with all of the above fixed, a reviewer at Nature Medicine/Lancet Digital Health/JAMA
will ask: "what clinical decision does this change?" Abnormal-vs-normal EEG classification does not, by
itself, change management — a clinician already reads the EEG and writes "abnormal." A model that predicts
what the clinician already determined has no workflow slot (it's not faster, not available before the read,
not resolving ambiguity) unless framed as (a) triage/prioritization of unread EEGs in a backlog, (b)
decision support in settings without EEG-boarded readers (rural/community hospitals — a genuine access
argument), or (c) a genuinely new construct (early/subclinical detection before the report is available, or
outcome prediction that a report label doesn't already contain, e.g., mortality risk that isn't literally
written in the read).

**The fix.**
- Anchor the paper's motivation on a decision or access gap, not a benchmark score: e.g., "EEG-boarded
  neurologist availability is a bottleneck at under-resourced/community hospitals; a frozen,
  CPU-trainable, cross-site-validated model could support triage or decision augmentation," and/or "predicts
  a clinical outcome (mortality/delirium-spectrum ICD) not contained in the EEG report itself, i.e. adds
  information beyond what the reader already determined" — the second framing is strictly better because it
  can't be dismissed as "reproducing the reader."
- This again argues for Section 7's recommendation: an ICD/mortality outcome is inherently a "so what" the
  report label is not.

---

## 7. RECOMMENDED PRIMARY OUTCOME + VALIDATION DESIGN (single most defensible)

**Primary outcome: cognitive/behavioral-syndrome spectrum (encephalopathy/delirium) ICD-10 diagnosis
within a pre-specified window of the EEG**, using `HEEDB_ICD10_for_Neurology.csv`'s Behavioral/Cognitive
Syndromes category, NOT the EEG report's normal/abnormal bit. Mortality (DateOfDeath) as a pre-registered
hard secondary outcome. Rationale:
- **Label validity**: an ICD-coded clinical diagnosis (or death) is not the same single-reader gestalt as
  the EEG report — it reflects a clinical team's determination over the full course, partially independent
  of the EEG reader's wording, which directly defeats the Section 3 attack.
- **Novelty**: per this repo's own gap analysis, no EEG foundation model has been externally validated
  against a clinical/neuro outcome (as opposed to an EEG-report-derived label) anywhere as of 2026 — this
  clears the Section 2 novelty bar cleanly, distinct from the "solved" TUAB abnormal/normal task.
  Mean-pool ceiling / MIL-head rationale still applies (diffuse background slowing = the encephalopathy
  substrate) and is architecturally the right match for an attention head over windows (diffuse, not
  necessarily localized-transient, so the MIL head's job is easier than for focal epileptiform detection).
- **Clinical "so what"**: predicting delirium/encephalopathy-spectrum risk or mortality from a routine EEG,
  externally validated, is a decision-relevant, non-tautological outcome (it is not already written in the
  EEG report), addressing Section 6 directly.

**Validation design (defeats Section 1 and Section 5 together):**
1. **Pre-register** primary outcome (encephalopathy/delirium ICD), secondary (mortality), model
   architecture, and site assignment via this repo's existing freeze/hash machinery, before touching test
   sites.
2. **Three-site design**, not two: **train on S0001**; **use I0002 as the tuning/validation site**
   (architecture, regularization, decision threshold selection only); report the **single confirmatory
   test on a third, never-touched site** (e.g., S0002 or an I00xx site with sufficient n). This directly
   defeats the ping-pong-artifact critique in Section 1.5 and matches this repo's own preregistered
   hospital-split confirmatory design.
3. **Site-invariance pipeline mandatory before any outcome model**: raw per-window tokens → `site_probe.py`
   audit (report the number) → `correct_sites.py` Route-A correction fit on train site only → re-audit with
   `site_probe.py`, gate at chance-tolerance AUC ≤0.58, published in methods → only then train the MIL head
   on corrected tokens. Bidirectional/multi-site cross-checks as in Section 1.
4. **Abnormal-vs-normal EEG retained only as a pre-specified calibration/sanity check** (Aim 0), explicitly
   subordinate to the primary outcome, reported with the caveat that it reproduces a single-reader label and
   is expected to sit below fine-tuned TUAB benchmarks.
5. **Report**: CONSORT/TRIPOD-AI-style inclusion flow diagram; bootstrap CIs on every AUC; in-sample vs. OOF
   gap on the head as a pre-registered go/no-go gate; site_probe pass/fail; bidirectional or 3-site results
   in full (not cherry-picked direction); all explored outcomes including prior nulls (seizure-disorder,
   abnormal-EEG) disclosed as secondary/exploratory with the primary clearly marked pre-registered.
6. **Honest framing**: contribution = first cross-site-external-validated EEG-foundation-model prediction of
   a clinical (non-EEG-report) neuro outcome, using a CPU-trainable frozen-encoder + MIL-head recipe;
   explicitly scoped below fine-tuned-encoder SOTA, with fine-tuning flagged as future GPU work.

---

## Priority summary

| # | Severity | Attack | Fix (one line) |
|---|---|---|---|
| 1 | CRITICAL | Site = hospital confound / shortcut learning | `site_probe.py` gate on raw + corrected tokens, `correct_sites.py` fit train-only, bidirectional + 3rd-site check |
| 2 | CRITICAL | Novelty — abnormal-EEG is solved (TUAB ~0.90) | Demote to calibration aim; primary outcome = clinical ICD/mortality, not report label |
| 3 | CRITICAL | Label validity — single-reader gestalt "abnormal" | Replace with ICD/death outcome, or at minimum quantify site/reader label-prevalence drift |
| 4 | MODERATE-CRITICAL | Frozen-head ceiling (mean-pool proven broken; MIL unproven at token level) | Re-run failure-analysis diagnostic ladder on token-level features feeding attention; pre-register honest sub-SOTA expectation |
| 5 | MODERATE | Selection/power/p>>n/multiplicity | Pre-register via freeze/hash; CONSORT flow diagram; bootstrap CIs; in-sample/OOF go-no-go gate before test-site unlock |
| 6 | MODERATE | Clinical "so what" | Frame as triage/access + outcome beyond what the report already states (ICD/mortality) |

**Recommended primary outcome:** cognitive/behavioral-syndrome (encephalopathy/delirium-spectrum) ICD-10
diagnosis (HEEDB `HEEDB_ICD10_for_Neurology.csv`), with mortality as a pre-registered hard secondary,
under a train-S0001 / tune-I0002 / confirm-on-a-third-site design with mandatory site-invariance
correction+audit before the outcome head is trained.
