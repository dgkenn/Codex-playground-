# HANDOFF — project state at R414 (2026-07-29)

*Read `CLAUDE.md` first. This document is the scientific state: what is established, what is provisional,
what is dead, and exactly what to do next. Every number here was verified against its raw log before being
written down.*

---

## 1. The one-paragraph state

The project is a burst-suppression and clinical-EEG research programme on HEEDB (49,232 patients with
reports), I-CARE (607 post-cardiac-arrest) and VitalDB (intraoperative). It has **414 logged results**. The
core prognostic claim — suppression burden stratifies outcome within the guideline's worst tier, adds over
the category, calibrates, and holds across hospitals and cohorts — is **solid and externally replicated**.
The mechanism work has eliminated most candidates and produced **one substantive lead at R389–R392: the
prognostic meaning of intra-burst EEG content reverses by aetiology.** That lead is internally robust and
externally under-supported, and closing that gap is the single most valuable next action.

**R404–R410 built a second story on top of that lead and then dismantled it. Read §3.0 before you touch
anything in that area** — three sessions of work now says the self-fulfilling-prophecy interpretation is
*not supported*, and the value of R404–R410 is the elimination, not a positive finding.

---

## 2. What is ESTABLISHED (safe to build on and to write up)

| claim | evidence |
|---|---|
| Burden stratifies 3-day death within the highly-malignant tier | 31.6 % → 73.4 % across quintiles |
| Burden adds over the guideline category, and is calibrated | +0.062 [+0.032, +0.095]; intercept −0.010, slope 0.979 |
| Holds across hospitals | 0.682 / 0.651 |
| Holds in a second cohort | I-CARE +34.1 pp [+23.2, +44.2] among the already-suppressed |
| **The inference machinery is calibrated** | `diff_ci` 0.045/0.065/0.065 vs nominal 0.05; `oob_increment` 0/60 vs nominal 0.025, mean null increment −0.0005 |
| **R360's residual is real, not a functional-form artefact** | linear −0.985 [−1.332, −0.665]; quintiles −1.030 [−1.386, −0.705]; deciles −0.993 [−1.360, −0.675]; **fully stratified, 5/5 burden strata negative and excluding zero** |
| BSP is interchangeable with a threshold ratio at ≥60 s windows, diverges below 30 s | r ≥ 0.98 at 60/120/300 s; crossover 15–30 s; 3.1× more accurate at 1 s |
| BSP's short-window advantage is **borrowed strength, not the model** | given identical data, `bsp_win`/ratio is 1.007–1.087 — never better, and worse as windows shorten |
| On real EEG a trailing ratio is **never** the best forward predictor | window-averaged causal BSP beats it at every window length, all paired CIs excluding zero |

---

## 3.0 STOP — the withdrawal/self-fulfilling-prophecy story was tested three ways and is NOT SUPPORTED (R409–R410)

Between R404 and R408 an attractive story was assembled: that the guideline EEG findings' aetiology-dependence
is partly manufactured by guideline-driven withdrawal of care, and that a clinician-**invisible** measure was
immune to it. **Do not present any of that.** It was tested directly and it failed.

| test | what it asked | result |
|---|---|---|
| **R409** paired landmark sweep | do visible flags attenuate more than the invisible measure, on *identical* patients? | **FALSIFIED.** Inside the withdrawal window no predictor of either kind falls below its matched null. Paired bootstrap P(invisible retains more at day 3) = 55 %, 44 %, 37 %, 36 %, 0 % — at or below chance against every flag. |
| **R409** structural check | can the comparison even be made? | **No.** Burst-suppression flag prevalence in the burst-morphology subcohort is **100.0 %** (2,473/2,473) vs 14.9 % overall — the invisible measure exists only *inside* the flag, so R407/R408's contrast compared two cohorts, not two predictors. |
| **R410** 72-hour hazard fingerprint | is there a decision-rule discontinuity where ERC-ESICM says to prognosticate? | **No.** Local excess 1.00 / 1.05 / 1.09 at days 2–4; largest anywhere in the cell 1.36 at **day 10**, [0.76, 2.33]. The primary bump statistic fired equally at a placebo cut, so it measured decay steepness, not timing. |
| direct measurement | is withdrawal in the data at all? | **Five failed proxies** — N14's four, plus `visit_disposition.discharge_to_source_value`, **100 % empty across 38,893 rows, 715 patients**. |

**What survives, and it is a single descriptive sentence:** burst suppression's aetiology interaction is
expressed inside days 0–4 and is spent by day 5 (retained 84 / 77 / 63 / **37** % at days 0–3, below its
size/event/aetiology-matched null at all eight landmarks), and the matched null sitting at ~100 % everywhere
shows that discarding 28 % of patients does not do this on its own. **Front-loaded hypoxic-ischaemic
mortality is now the parsimonious explanation and should be stated as the primary reading.**

**Why R404–R410 was still worth doing.** It closed the most obvious reviewer objection to the lead — "isn't
this just self-fulfilling prophecy?" — by showing the data cannot support that reading either, and it
produced the matched-null machinery that makes any future landmark claim in this project interpretable.

---

## 3. The LEAD (R389–R403) — internally robust, externally weak, and ONE ARM IS WITHDRAWAL-VULNERABLE

> **READ THIS BEFORE QUOTING THE LEAD (R403, strengthened by R411).** The two arms of the reversal are not
> equally robust to the self-fulfilling-prophecy problem. Among patients **alive at day 3** — past the window
> in which most withdrawal of care happens — the **non-anoxic (protective) arm survives** at 0.428 [0.388,
> 0.471], while the **anoxic (harmful) arm does not**: 0.535 [0.492, 0.580], interval including 0.5, on 800
> patients.
>
> **R411 tested whether that was merely a power artefact of splitting the cohort, and it is not.** Drawing
> subsamples of the *full* anoxic arm at the landmark's size (800) and event rate (35.1 %), with no landmark
> applied, only **1 %** have an AUC interval including 0.5 — and the non-anoxic arm's figure is **0 %**. The
> drop from 0.577 to 0.535 is about *which* patients were removed, not how many. **This caveat is now better
> evidenced than when it was first written; do not soften it.**
>
> **R411 also resolves the apparent conflict with R409.** The interaction — which is the lead's actual
> estimand, since the claim is that the *direction* differs — retains 93 % and still excludes zero
> (+4.646 [+3.092, +6.547] full; +4.313 [+2.335, +6.481] past the landmark). It survives because the
> non-anoxic arm is unmoved (0.426 → 0.428). **So: the reversal survives the withdrawal window, and the
> anoxic arm's information is genuinely concentrated in early deaths.** Both sentences, together.
>
> That concentration in early deaths is both what a partial self-fulfilling prophecy would produce and what
> genuine early post-anoxic mortality would produce, and this design cannot separate them (N14). **R410
> attempted the separation via a timing fingerprint and failed to find one** — no local hazard discontinuity
> at 72 h or anywhere else — so with no timing signature and no measurable withdrawal variable, **front-loaded
> hypoxic-ischaemic mortality is the parsimonious reading and should be stated first.** The honest headline is
> a reversal whose protective arm is robust to the withdrawal window and whose harmful arm is carried by early
> deaths that this design cannot attribute. That belongs in an abstract, not a limitations paragraph.
>
> What still stands: the full-cohort reversal with all its robustness checks, and W1 — adjusted for the flags
> clinicians actually recorded, the interaction is **+4.287 [+2.535, +6.560]**, so it is not a proxy for what
> the decision process saw.

> **R413 — a specificity check the lead now carries.** Tested on an independent instrument (burst
> amplitude, r = −0.023 with intra-burst content), the reversal **does not reproduce**: +0.256
> [−0.494, +0.796] against the reference +0.913 [+0.574, +1.336] on the same cohort and adjustment.
> Model-free, intra-burst content is the **only one of six morphology measures** whose two aetiology arms
> sit on opposite sides of 0.5 with both intervals excluding it. This removes the worry that the reversal is
> an artefact of one computed number, and points a mechanism toward frequency content rather than signal
> scale. **It is a failure to replicate, not a demonstrated absence** — the upper bound is 87 % of the
> reference effect.

> **R414 — the pharmacological objection is retired, and the result went the other way.** Intra-burst
> 8–30 Hz sits where propofol works, so the obvious reviewer question is whether the reversal is a drug
> signature. It is not. Sedation prevalence differs between arms by only 9.8 pp and shifts the measure by
> 0.097 SD, and **where no BS-capable agent was running the reversal is present and wider**: anoxic AUC
> **0.647 [0.553, 0.746]** vs non-anoxic **0.339 [0.259, 0.432]**, a gap of **0.308** against **0.151** in
> the sedated stratum. A matched null shows a stratum this size (n = 286) fails by chance 25 % of the time,
> so passing it is meaningful. **Quote the AUC gap, not the coefficients** (+12.6 vs +3.5) — logistic
> coefficients are not comparable across strata with different outcome variance. The clinical reading:
> the reversal is strongest where suppression is **pathological rather than iatrogenic**.

### The original statement of the lead

**Intra-burst 8–30 Hz content ranks 30-day death in opposite directions by aetiology.**

| | n | AUC | direction |
|---|---|---|---|
| anoxic | 818 | **0.589 [0.545, 0.633]** | more fast content → **more** death |
| non-anoxic | 679 | **0.408 [0.364, 0.452]** | more fast content → **less** death |

**Survives every artefact test applied:**
- Non-parametric — no model, no link function, no adjustment.
- **Burden strata 3/3** (median burden differs sharply: 0.445 anoxic vs 0.086 non-anoxic).
- **Burst-count strata 3/3** — the variable that actually gates the L1 exclusion, which differs by aetiology
  (55.7 % vs 89.5 % excluded). The effect *strengthens monotonically* with burst count in both directions:
  anoxic 0.536 → 0.603 → 0.635, non-anoxic 0.406 → 0.419 → 0.390.
- **Decomposition of the non-anoxic arm, 4/4 below 0.5, clustered within 0.028:** sepsis 0.427 [0.363, 0.494],
  metabolic 0.410 [0.358, 0.462], structural 0.399 [0.344, 0.454], status 0.406 [0.320, 0.501].

**It retrodicts N10**, a standing negative it was not constructed to explain: morphology's predictive
increment was +0.070 [+0.006, +0.121] in I-CARE (entirely cardiac arrest) but +0.036 [−0.019, +0.076] in
HEEDB (54.6 % anoxic). A mixed cohort averages two opposing effects toward zero.

**The companion finding (R389, now corroborated by R396):** the clinician slowing flag's protective effect is
genuinely larger after anoxia — interaction **−0.750 [−1.433, −0.116]** — which a generic-severity account
does not predict. **Sleep spindles, whose generator is anatomically known (thalamic reticular nucleus),
independently agree: interaction −0.296 [−0.548, −0.052] on 8,349 patients.** Two instruments sharing no
method make the same prediction that generic severity does not.
Consistent with a thalamocortical explanation and with Schiff's mesocircuit framework (**PMID 31994749**,
verified from MEDLINE).

### What is wrong with it, stated plainly

*Updated at R393–R394: weaknesses 3 and 4 below are now TESTED and survived. Only the first remains.*

1. **External replication is weak, and this is now the ONLY remaining caveat.** I-CARE AUC is **0.511 [0.464, 0.557]**
   — it *includes* 0.5. It agrees in direction only. Worse, I-CARE is entirely cardiac arrest, so it is
   **structurally incapable** of testing an aetiology contrast; it can only ever test one arm.
2. **The registered rule was too weak.** It required only directional external agreement, and passed on
   evidence that establishes almost nothing. Catalogue rule 30 exists because of this.
3. ~~**Death-ascertainment conditioning (L3)** applies to every estimate.~~ **CLOSED PROPERLY (R398–R399),
   after R393's version turned out to rest on a wrong assumption.** The decedents-only restriction was an
   extraction artefact: re-extracting `condition_occurrence` against all 2,473 morphology patients gave 953
   of the 954 survivors an aetiology they had never had. They are **38.7 % anoxic**, so R393 had ~369
   patients in the wrong arm. On measured labels the reversal holds — anoxic n=1,187 **0.577 [0.547, 0.608]**
   versus non-anoxic n=1,262 **0.426 [0.392, 0.461]** — and correcting the misassignment moved the gap only
   from +0.157 to +0.151. **L3 is lifted for aetiology, not for outcome ascertainment.** Superseded text
   follows for the record: **(R393).** Rebuilt on the
   full 2,451-patient cohort treating an absent death record as alive: anoxic 0.589 [0.545, 0.633] versus
   non-anoxic 0.432 [0.397, 0.465]. The two analyses have opposite ascertainment biases and agree.
   *Qualification:* ascertainment is 100 % in anoxic and 41.6 % in non-anoxic, so the anoxic arm is identical
   either way and R393 in fact tests the non-anoxic arm only — expanding it from 679 to 1,633.
4. ~~**Aetiology comes from ICD codes.**~~ **CLOSED (R394).** Split into arrest codes (0.592 [0.545, 0.639])
   and encephalopathy codes (0.608 [0.554, 0.659]), each against patients with neither family. Both confirm,
   so the finding does not rest on one code list.
5. **It is effect modification, not a mechanism.** It says the same measurement means opposite things in two
   populations; it does not say why.

---

## 3b. THE SECOND FINDING (R404–R406) — guideline transfer, n = 9,302

Five of six ACNS findings behave differently by aetiology, four surviving adjustment for measured burden.
Pre-specified primary: **burst suppression predicts death after anoxia (+0.47 [+0.29, +0.66]) and carries
essentially nothing otherwise (+0.05 [−0.06, +0.16])**, interaction +0.42 [+0.20, +0.64]. **LPD reverses
sign** (−0.25 anoxic vs +0.28 [+0.16, +0.41] non-anoxic).

**R407 sharpens this.** Estimating each interaction again among patients alive at day 3: **burst suppression
retains only 37 %** and its interaction no longer excludes zero (+0.15 [−0.09, +0.41]), while the **invisible
intra-burst measure retains 93 %** and still does. Burst suppression is the one finding guidelines name as a
withdrawal trigger after cardiac arrest; focal slowing, which no guideline actions, retains 95 %. The gradient
tracks how strongly each finding is guideline-actioned. *(The pooled visible-vs-invisible comparison is weak —
ranges overlap — so quote the per-finding gradient, not an average.)*

**Do not report this without its second reading.** These are the flags clinicians read, and guidelines tell
them to act on burst suppression after cardiac arrest and not otherwise — so "predicts death only after
anoxia" is exactly what guideline-driven withdrawal would manufacture. The tie-breaker is that the
**invisible** intra-burst measure shows the same dependence and cannot be behavioural (+4.287 [+2.535,
+6.560] adjusted for these flags, R400). The two must be presented together.

---

## 4. What is DEAD — do not revisit

| candidate | why |
|---|---|
| Whole-record background spectrum as the flag-residual explanation | B3: mutually redundant with the intra-burst measure |
| Spatial topography | T3: +0.014 [−0.021, +0.040] over burden + background + intra-burst |
| Within-hour temporal trend | R377: −0.478 [−1.645, +0.748] |
| The flag/intra-burst "one factor" unification (R358–R360's interpretation) | R389/T2: their aetiology interactions have opposite signs |
| MORGOTH's label sets as a fix for the slowing flag | R385: positives-only, and FOCALSLOWING patients are *also* 99.8 % gen-slowing-flagged — the number measured the population, not the concordance |
| The MORGOTH model itself | code and checkpoint unreleased; cannot be verified from the sandbox (GitHub access is proxy-scoped) |
| BSP beating a threshold ratio at recording level | r = 0.988, increment −0.010 [−0.021, +0.004] |
| Separating withdrawal from biological death | N14: four instruments, one root cause |

**Also confirmed alive:** the across-days trend (R378) — burden falls faster in good outcome, trend
coefficient **+1.061 [+0.233, +2.057]** adjusted for burden, background and intra-burst content, robust to
raw-vs-rate scaling. But **every out-of-bag increment includes zero**: association without discrimination
gain, and the estimand is restricted to patients who survived to be measured twice (availability is
outcome-related, −17.6 pp [−25.5, −9.1]).

---

## 5. What to do next, in order

**0. Replicate the aetiology reversal in a mixed-aetiology cohort. This is the gate on everything else, and
   it is now the ONLY open weakness.**

   **CORRECTION (2026-07-27): TUH is NOT the answer, and an earlier version of this document wrongly said it
   was.** The TUH EEG Corpus carries **no linked outcome data** — its manifest is `recording_id, patient_id,
   edf_path, sfreq, age, sex` — and no diagnosis field either. It cannot replicate an outcome association at
   any effort, let alone an aetiology contrast. **This was already established in this ledger at R321** and
   should have been checked before TUH was recommended.

   **There is no known cohort with EEG + outcome + mixed aetiology other than HEEDB.** LESSONS records the
   same gate independently: "no external dataset with EEG + hard-outcome + a 2nd site". So the strongest
   available test is the **hospital split inside HEEDB** (S0001 vs S0002) — weaker than a true external
   cohort, and honest about being so. Anything stronger requires a data-access change, not an analysis.

**~~1. Remove the death-ascertainment conditioning.~~ DONE — R393, survived.**

**~~2. Re-derive aetiology against a second definition.~~ DONE — R394, both code families confirm.**

**~~3. The spindle test.~~ DONE — R395–R396.** Spindles carry outcome information beyond burden
   (−0.772 [−0.876, −0.672], n = 8,349) and the aetiology interaction confirms (−0.296 [−0.548, −0.052]),
   converging with R389's flag result from an anatomically specific instrument. **Caveat:** under the
   aggressive `awake` adjustment the main effect survives (−0.450 [−0.573, −0.329]) but the interaction goes
   marginal (−0.252 [−0.507, +0.001]).

**4. (was 3) The spindle test — superseded, see above.** `docs/research/48_RESEARCH_LANDSCAPE.md` §B: sleep spindles are generated by the
   thalamic reticular nucleus and are annotated on 49,232 patients (43.5 % prevalence, n = 6,891). They are a
   far better instrument for the thalamocortical account than the slowing flag. **The confound is severe and
   must be handled up front:** sleep architecture requires a patient who cycles, so "spindles present" is
   substantially "not deeply encephalopathic". The question is whether spindles carry information *beyond*
   depth and whether that residual is aetiology-dependent.

**4. Waveform shape rather than band power** — the last untested candidate for the flag residual. Stereotypy
   at 1 s and 2 s is already extracted and is the nearest existing handle.

---

## 5b. RE-RANKED after the R400–R411 cadence (2026-07-28) — read this instead of the list above

The withdrawal thread is **closed** (§3.0): three tests, no support, and the elimination is the deliverable.
That frees the queue. Ranked by (mechanism named + reference in the data + sharp falsifiable prediction):

| # | item | why it ranks here |
|---|---|---|
| ~~1~~ | ~~Waveform shape~~ — **DONE, R412** | Stereotypy contributes **+0.0088**; **burst amplitude** contributes **+0.0783** of a **+0.1186 [+0.0501, +0.1998]** total, outside a permutation placebo and not a site gain artefact. Amplitude is a scale parameter, not shape, so the named candidate is eliminated and **89 % of the residual survives**. The flag residual is now a **standing negative with no named candidate left** — see the box under this table. |
| **2** | **Does the anoxic arm's early-death concentration have a dose-response in TIME?** | R411 established the concentration is real and not power. The untested follow-up: does the arm's AUC decline smoothly with landmark day, or step? A step at a clinically meaningful day is the one remaining handle on cause, and the matched-null machinery (R408) now makes it interpretable. Cheap — all data local. |
| **3** | **Aetiology reversal, hospital split, with the matched null** | S0001 vs S0002 is the strongest external check that exists (no cohort anywhere has EEG + outcome + mixed aetiology — §5 item 0). R397 ran it without a matched null; re-running with one would say whether any site difference exceeds what site-size differences produce. |
| **4** | Spindles beyond depth (item 4 above) | Done in part at R395–R396; the aggressive-`awake`-adjustment caveat is the open piece. |

> ### The flag residual is now a STANDING NEGATIVE, and that makes it the most valuable target here
>
> All four named candidates are closed: background spectrum (B3, R361–R364), topography (T3, R365–R368),
> **waveform shape/stereotypy (R412 — contributes +0.0088)**, and reactivity (unavailable in this schema).
> R412's only positive is **burst amplitude**, worth **+0.0783** of a **+0.1186 [+0.0501, +0.1998]** total
> attenuation — real, outside a permutation placebo, not a site gain artefact, and **leaving 89 % of the
> residual standing**.
>
> The clue worth working from: amplitude is **near-orthogonal** to everything already adjusted for
> (r = −0.0001 with burden, −0.023 with intra-burst content). Whatever the clinician is reading is not a
> re-expression of burden or of spectral content, and is at least partly about **signal scale**. A fifth
> candidate should be sought in that direction. Per the ten-result cadence, **a finding that retrodicts this
> negative is worth more than one that adds a positive.**

**Do not re-open:** withdrawal proxies (six failures now), TUH as an outcome cohort (no outcome data — R321),
visible-versus-invisible contrasts (R409), 72-hour timing fingerprints (R410).

---

## 6. Traps that will cost you time

- **`/tmp/eeg_probe/` is ephemeral.** See CLAUDE.md. The HEEDB burden and morphology shards are hours of work.
- **Always use `scripts/heedb_run.sh`.** Placeholder env credentials outrank profiles and produce a 403 that
  looks exactly like expiry.
- **The morph/burden files are FOUR DISJOINT SHARDS.** Using `s0` alone gives n≈239 and is underpowered —
  that mistake made R387 inconclusive. Glob `*.s*.csv`.
- **The `hour` column in the cached I-CARE burden files is the ACTUAL hour of the nearest recording, not the
  target.** 15.4 % of "h12 vs h24" pairs are the same file differenced against itself.
- **R358–R360 has no committed script.** Commit `dcc3700` changed only the ledger, so its n = 818 cohort is
  not recoverable. Anything claiming to replicate it should say so.
- **1 GB OMOP scans** — cache the aetiology map (`heedb_aetiology_full.csv`) rather than re-scanning.
- **Report-text findings are read live from S3**, not cached: `EEG/HEEDB_Metadata/{S0001,S0002}_EEG__reports_findings.csv`.
  Useful columns include `normal, abnormal, awake, n1, n2, bets, wicket, spindles, vertex wave, posts, bs,
  gpd, lpd, seizure, gen slowing, foc slowing`.

---

## 7. How to reproduce the lead from scratch

```bash
# 1. aetiology cache (~3 min, scans a 1 GB OMOP table, then cached)
scripts/heedb_run.sh python analysis/heedb_content_by_aetiology.py    # builds heedb_aetiology_full.csv

# 2. the reversal and its full red-team  (needs heedb_burst_morph.s*.csv + heedb_bs_burden_win.s*.csv)
scripts/heedb_run.sh python analysis/heedb_content_sign_flip.py

# 3. the aetiology fork that produced it
scripts/heedb_run.sh python analysis/heedb_thalamocortical_test.py

# 4. the R360 verification it depends on
scripts/heedb_run.sh python analysis/heedb_flag_burden_nonlinear.py

# supporting: BSP window question, both arms
SWEEP_T=1200 SWEEP_SEEDS=12 python analysis/bsp_window_sweep.py
python analysis/bsp_window_real.py                  # needs icare_suppseq.csv + icare_seq_keep.csv
```

Every one of these carries its pre-registration in the module docstring, committed before its result existed.
Read the docstring before reading the output — it states the falsification condition and the scope limit.

---

## 8. Session log for R365–R392 (2026-07-27)

| results | what |
|---|---|
| R365–R368 | Topography eliminated as the flag-residual explanation |
| R369–R370 | Both inference procedures audited against permuted labels — calibrated |
| R371–R372 | Time-axis defect found by reading our own extraction code; 73/602 excluded, exclusion is outcome-related |
| R373–R376 | BSP window-length sweep in simulation; `47_BSP_TECHNICAL_NOTE.md` §5.3 answered and retired |
| R377–R380 | Temporal evolution: null within an hour, confirmed across days |
| R381–R384 | BSP window question on real EEG, scored by forward prediction |
| R385–R387 | MORGOTH labels cannot fix the slowing flag; the flag is strongly burden-dependent; a threat to R360 raised and left inconclusive |
| R388 | R360 verified — the residual survives flexible and fully stratified burden adjustment |
| R389–R392 | **The aetiology reversal** |

Six registered predictions were refuted this session, including three of my own: BSP's like-for-like
advantage, the flag/intra-burst unification, and the spatial-dispersion direction. The reversal was found by
a check registered to test something else.
