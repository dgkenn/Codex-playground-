# STATS_CODE_AUDIT.md — Adversarial correctness audit of headline-claim analyses

Hostile statistical review (correctness only) of the modules behind the paper's
five headline claims. Focus: data leakage in CV, target overlap/circularity,
denominator/filter bugs, bootstrap/CI correctness, multiple-testing surface,
mortality-merge correctness. Probes were run from repo root against the live
caches (`cache/`, MIMIC raw in scratchpad). Throwaway probes in scratchpad.

**Bottom line up front:** the headline conclusions **survive**. One construct-
validity number is circular and presented as supportive (MODERATE), one reported
sensitivity/specificity pair is in-sample/optimistic (MODERATE), and there are
several non-conclusion-changing clustering/ordering issues (MINOR). No CRITICAL
bug that flips a headline was found. The two external replications, the within-
patient reliability, and the early→late prediction hold up under the probes.

---

## Findings table

| # | Module | Issue | Severity | Conclusion moves? |
|---|--------|-------|----------|-------------------|
| 1 | pressor_requirement.py | `construct_validity vs_cumulative_exposure` (+0.69) is **mechanically circular** — cumulative exposure = Σ(dose×dur) over the *same* NEPI epochs whose median dose *is* the phenotype. On disjoint epochs it collapses to +0.02. Presented in the GO verdict as supporting evidence. | **MODERATE** | No (GO survives on reliability), but the number is not evidence |
| 2 | pressor_requirement.py | `vs_EV1000_SVR` = **+0.182**, but the code's own `note` predicts NEGATIVE ("low tone = high requirement"). The failed-direction construct check is quoted in the GO verdict as if confirmatory. | MODERATE | No (n=15, not in GO logic), but mis-stated |
| 3 | early_id_robustness.py | `test_operating_point` reports **sensitivity 0.72 / specificity 0.62 in-sample**: threshold = `median(early)` chosen on the full cohort, applied to the same cohort. AUC (0.771) is rank-based and honest; the sens/spec pair is optimistic. | **MODERATE** | No (AUC unaffected), but sens/spec are not CV |
| 4 | mimic_external_validation.py | `_mortality`: one row per **stay**; patients with multiple stays appear multiple times (2,402 duplicate-subject rows) and bootstrap resamples stays, not subjects → understated CI. Probed: patient-clustered CI [3.45, 4.19] vs reported [3.44, 4.17]; one-row-per-subject OR 4.17. | MINOR | No — OR robust |
| 5 | mimic_external_validation.py | `trait_across_stays` uses `reqs[0], reqs[1]` in **dict-insertion order** (not chronological), only first two stays. Symmetric Spearman → only adds noise. | MINOR | No |
| 6 | external_validation_inspire.py | `_trait_across_ops` pairs `iloc[0], iloc[1]` (row order, not op date/`op_id`), first two ops only. Symmetric → noise only. Minor n discrepancy (218 vs 219, dropna). | MINOR | No |
| 7 | requirement_specificity.py | `attack4_selection` composite-rate denominators differ (incl n=34 vs excl n=16, not all 52/23) because composite is missing for some cases; rate-ratio 1.41 still directionally fine. Disclosed as bounding generalizability. | MINOR | No |
| 8 | concordance_outcome.py | `_assign` uses **full-cohort medians** to define `reco`/`actual`, and `_gcomp_rd` standardizes X once on full data then reuses inside the bootstrap. These are exposure-definition / g-comp choices, not a CV target leak; verdict is NULL and direction is +RD (concordant slightly *more* injury). | MINOR | No — null is robust, can't false-positive |
| 9 | independent_svr_validation.py | Cohort is **70% liver transplant (62/89)** — heavy case-mix confound for a tone↔SVR claim; airtight tests (`tau_partial|MAP+HR`=0.045, body-size attack C `pass:false`) largely fail. All disclosed; OOF uses per-fold scaling (no leakage). | MINOR | No — module already honest/cautious |

---

## Per-module detail

### 1–2. pressor_requirement.py — the requirement phenotype (Claim 1)
**Clean parts.** Stable-epoch extraction is sound: `_segments` finds maximal
constant-rate runs ≥`MIN_EPOCH`, `SETTLE`=60 s drops the settling transient,
`norepi_only` correctly checks *other* vasoconstrictors are off in the epoch
(`_rate_at` over [t0,t1]). Per-kg dosing, MAP-band conditioning, physiologic
gates all present. Split-half reliability (`_icc_splithalf`, odd/even epoch
medians, Spearman 0.817) is a legitimate within-patient trait check and is the
load-bearing evidence. The dose-response-gain cluster bootstrap resamples on
`caseid` (correct unit).

**MODERATE — circular construct validity (issue 1).** `cum[cid] = Σ(dose_per_kg
× dur)` over NEPI epochs, correlated against the phenotype `median(dose_per_kg)`
over the target-band NEPI epochs. The two share the same dose values, so the
+0.69 is largely tautological. Probe (`scratchpad/probe2.py`):
- as-coded (overlapping epochs): **+0.69** (n=52)
- disjoint (cumulative over non-target-band epochs only): **+0.02** (n=37)

The GO logic is `spread_ok AND abundant_ok AND (reliable_ok OR construct_ok)`.
`construct_ok` (cumulative > 0.2) is satisfied only by this circular number, but
`reliable_ok` (split-half 0.817 ≥ 0.4) independently satisfies the OR, so **GO
does not depend on the circular term**. The fix is presentational: drop/relabel
the cumulative-exposure "construct validity" or compute it on disjoint epochs.

**MODERATE — wrong-sign SVR check quoted as supportive (issue 2).** Probe
(`scratchpad/probe1.py`) confirms `vs_EV1000_SVR` = **+0.182** while the code's
own note predicts negative. The verdict string lists it among markers the
phenotype "tracks," which is misleading (n=15; also EV1000 SVR is itself
waveform-derived/circular per the SVR module). Not in GO logic; conclusion holds
on reliability + spread, but the sentence overstates construct validity.

### 3. early_id_robustness.py — early predicts late (Claim 1/3)
**Clean parts.** `_oof_spear` puts SimpleImputer + StandardScaler + RidgeCV
**inside** a Pipeline fit per fold → no imputation/scaling/alpha leakage. early
(first-half median) and late/`hi` (second-half) are **disjoint** epoch sets — no
target overlap. `base_map`/`tone` are whole-case features fed only into the
*clinical baseline*, which can only make the incremental-over-clinical test more
conservative (they cannot inflate the A-line arm). The incremental result
(−0.01 → +0.19) is a real OOF lift.

**MODERATE — in-sample operating point (issue 3).** `test_operating_point`
picks the threshold as `median(early)` over the full cohort and scores sens/spec
on that same cohort. Probe (`scratchpad/probe_op.py`) reproduces AUC 0.771 and
in-sample sens 0.72 / spec 0.62. The AUC (rank statistic) is the honest summary
and is unaffected; the sens/spec pair is optimistic and should be labeled
in-sample or replaced with a CV/LOO threshold. Does not change the conclusion
that early dose discriminates eventual high-requirement (AUC).

### 4–5. mimic_external_validation.py — external replication (Claim 2)
**Clean parts.** `filter_norepi` keeps only `kg`-unit rows (`"kg" in uom`),
correctly excluding mcg/min — the unit-filter bug the prompt flagged is **not**
present. `_stays` gates 0<rate≤5 mcg/kg/min and time-sorts segments; early/late
split is genuinely time-ordered and disjoint. Mortality merge keys are correct:
`stay_id → hadm_id` (icustays) → `hospital_expire_flag` (admissions),
`subject_id → anchor_age` (patients); `hospital_expire_flag` read as the death
label is the right semantics.

**MINOR — row-level non-independence (issue 4).** Reliability, early→late, and
mortality treat stays as independent; 2,402 of 15,949 rows are repeat subjects,
and bootstraps resample rows/stays not patients. Probe (`scratchpad/probe_mort.py`):
patient-clustered OR CI [3.45, 4.19] ≈ reported [3.44, 4.17]; collapsing to one
row per subject gives OR **4.17** — if anything stronger. **Conclusion robust.**
The huge OR (3.8/SD, ΔAUC +0.205 over age) is severity confounding, openly
caveated, not a bug. Separately, the autocorrelation concern on early→late is
already addressed by `autocorrelation_attack.py` (time-gapped early→late stays
positive out to ≥12 h; shuffled nulls ≈0; within-stay CV median 0.51 so not
trivially constant).

**MINOR — arbitrary stay ordering (issue 5).** `trait_across_stays` uses
insertion-order first-two stays; Spearman is symmetric so this only adds noise
(and trait-across-stays is the weakest leg, r=0.12, honestly reported).

### 6. external_validation_inspire.py — external replication (Claim 2)
**Clean.** OOF AUC pipeline scales/imputes per fold (no leakage). Outcome merges
on `subject_id`. The verdict honestly reports the incremental-over-MAP as **null**
(ΔAUC 0.002–0.004) rather than spinning it. Trait-across-operations replicates
(duration-normalised Spearman +0.32, CI [0.19, 0.44]); probe reproduces +0.319.
Issue 6 (row-order pairing) is symmetric-correlation noise only.

### 7. requirement_specificity.py — specificity battery (Claim 3)
**Clean / strong.** Partial-Spearman via rank-residualisation is correct; early
vs late halves are disjoint and time-ordered. Attacks reproduce: partial
(controlling early MAP+HR) **+0.466**, placebo MAP −0.40 / HR −0.01, case-mix
exclusions hold (+0.54 each), jackknife min r +0.51. The OOF-increment leg is
honestly marked "weakened" (−0.047) — no p-hacking; the module does not cherry-
pick a passing definition. Issue 7 (selection denominators) is a disclosed
generalizability bound. The lead specificity claim survives.

### 8. concordance_outcome.py — null decision-benefit (Claim 4)
**Clean for its conclusion.** g-computation RD, case bootstrap, negative control
(`organ_coagulation`), E-value all present. Median-split exposure definitions and
once-computed standardization are not CV-target leaks. The verdict is **NULL**
(adj composite RD +0.052, CI [−0.118, 0.211]) and the point estimate sign is
*positive* (concordant slightly more injury), so no bug here could manufacture a
false benefit. A null that should be null. Robust.

### 9. independent_svr_validation.py — tone vs independent SVR (Claim 5, skim)
**Honest/cautious.** OOF Ridge scales per fold; permutation null and bootstrap CI
present. The module's own results show the airtight tests largely fail
(`tau_partial|MAP+HR`=0.045; body-size attack C `pass:false`;
`pure_shape_incremental_over_pressure+HR`=−0.034) and the doc does not overclaim.
Main weakness — 70% liver-transplant cohort (n=89) — is disclosed. No conclusion-
changing correctness bug.

---

## Overall verdict

**The headline conclusions are robust to the bugs found.**

- **Claim 1 (requirement is a reliable trait; early→late):** survives. Rests on
  within-patient split-half reliability (0.82) + spread + early→late (+0.54,
  partial +0.47), all of which reproduce. The *construct-validity* support is
  weak/misstated (issues 1–2) but is not what the claim hangs on; recommend
  rewording the verdict and dropping the circular cumulative-exposure number.
- **Claim 2 (external replication):** survives, and is the strongest part. INSPIRE
  trait +0.32 and MIMIC reliability 0.95 / early→late 0.62 / mortality OR ~3.8
  all reproduce; mortality OR is robust to patient-level clustering.
- **Claim 3 (specificity / incremental-over-clinical):** survives. Partial-r and
  placebo/case-mix/jackknife attacks reproduce; OOF increment honestly "weakened."
- **Claim 4 (null decision-benefit):** survives — a genuine null with the point
  estimate in the *non*-beneficial direction; not gameable into a positive.
- **Claim 5 (tone vs independent SVR):** the module is already appropriately
  hedged; nothing inflated.

**Required fixes (none flip a headline, two are honesty-of-reporting):**
1. pressor_requirement.py — recompute or remove the cumulative-exposure
   "construct validity" (circular: +0.69 → +0.02 on disjoint epochs); correct the
   verdict's claim that the phenotype "tracks EV1000 SVR" (sign is +0.182, wrong
   direction, n=15).
2. early_id_robustness.py — label the operating-point sensitivity/specificity as
   in-sample, or derive the threshold out-of-fold.
3. (optional) cluster MIMIC bootstraps on `subject_id`; order INSPIRE/MIMIC
   multi-op/multi-stay pairs chronologically (`op_id`/time) for cleanliness.

_Probes: scratchpad/probe1.py (SVR sign), probe2.py (cumulative-exposure
circularity), probe_op.py (in-sample operating point), probe_mort.py (MIMIC
mortality clustering), probe_insp.py (INSPIRE trait). All run from repo root._
