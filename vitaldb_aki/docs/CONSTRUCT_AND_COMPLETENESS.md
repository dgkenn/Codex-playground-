# Construct-consistency audit + completeness critique (harshest-reasonable-reviewer pass)

Two jobs: (A) do the VitalDB and MIMIC "requirement" findings measure the SAME
construct, and (B) what is the single biggest remaining hole a top-journal
reviewer would still raise. No claim is taken at face value; estimands are read
off the code, not the prose.

Source of truth for the estimands:
- VitalDB: `analysis/pressor_requirement.py` (stable-epoch extractor + phenotype).
- MIMIC: `analysis/mimic_external_validation.py` (`_stays`/`compute`),
  `analysis/mimic_outcomes_doseresponse.py`, `analysis/mimic_severity_scores.py`,
  `analysis/mimic_early_warning.py`, `analysis/mimic_subgroups.py`.

---

## A. CONSTRUCT-CONSISTENCY AUDIT

### A.1 Are the two "requirements" the same estimand? NO — they are two different
estimators of a loosely shared concept.

Read directly from code:

**VitalDB requirement** (`pressor_requirement.py`):
`median over a patient's STABLE, constant-rate, norepi-ONLY epochs of
(device_rate / weight), restricted to epochs whose sustained MAP falls in
[55, 80] mmHg, first 60 s post-rate-change dropped (SETTLE), epoch >= 180 s,
>= 6 MAP samples, >= 2 qualifying epochs.`
The defining machinery is: (i) **stable-epoch detection** (maximal constant-pump-
rate runs), (ii) **MAP-band conditioning** (only epochs holding MAP in target),
(iii) **single-agent** conditioning, (iv) a **settle delay**. This is a
*level-on-level, MAP-conditioned dose* designed to be closed-loop-free.

**MIMIC requirement** (`mimic_external_validation.py:_stays`/`compute`):
`median over ALL of a stay's norepinephrine infusion segments of the
per-kg rate (mcg/kg/min), gate 0 < rate <= 5.`
There is **no stable-epoch detection** (every charted segment counts, including
active up/down-titrations), **no MAP-band conditioning** (MAP is never pulled —
see A.2), **no settle delay**, and the only conditioning is "this is a
norepinephrine segment with a kg-normalised unit."

These differ on **every one of the four conditioning steps that the VitalDB
document advertises as the thing that makes the metric meaningful** (per-kg is the
only shared step). Concretely:

| Conditioning step | VitalDB | MIMIC |
|---|---|---|
| Stable / constant-rate epoch detection | YES (load-bearing) | NO (all segments) |
| MAP held in target band [55,80] | YES (load-bearing) | NO (no MAP at all) |
| Single-agent (norepi-only) | YES | NO (norepi segments, co-pressors not excluded) |
| Settle delay (drop 60 s post-change) | YES | NO |
| Per-kg normalisation | YES (rate/weight) | YES (already mcg/kg/min) |

**Verdict A.1: the cross-cohort agreement is a *conceptual analogy*, not an
apples-to-apples replication.** What replicates is the coarse claim "median per-kg
norepinephrine dose is a reliable, early-identifiable, mortality-stratifying
patient-level summary." What does NOT cross over is the *specific estimand the
VitalDB paper spent its mechanistic argument on* — the MAP-conditioned,
stable-epoch "controller-effort" dose. The MIMIC metric is a plain dose-intensity
summary; the VitalDB metric is a deliberately de-confounded dose. The MIMIC result
is genuine and valuable external evidence that *dose intensity travels*, but it
does not validate the *de-confounding* that is the VitalDB paper's intellectual
contribution.

This is **not fatal**, but it is currently **over-framed**. The HOSTILE_REVIEW_
SURVIVAL row #4 ("Single-centre -> MIMIC reliability 0.95, early->late 0.62 ->
SURVIVES") and the abstract-level "externally replicated (OR+ICU, n>16k)" both
read as if the *same* phenotype was reproduced. It was not. A sharp reviewer who
opens both functions will catch this in five minutes and will (rightly) accuse the
paper of equivocating on what "the requirement" means.

**Recommended honest framing.** State it as a **two-level claim**:
> "The *general* property — that a simple per-kg norepinephrine dose summary is a
> reliable, early-identifiable, mortality-graded patient signal — replicates in an
> independent ICU cohort (MIMIC-IV, n=15,949). The *specific* MAP-conditioned,
> stable-epoch estimand developed in VitalDB (the 'controller-effort' dose) is
> **not** reproduced in MIMIC, where MAP and constant-rate epochs are unavailable;
> the MIMIC metric is a coarser whole-stay dose intensity. The replication is
> therefore of the phenotype's *robustness as a dose summary*, not of the
> control-theoretic de-confounding."

A cheap (not run here) test that would materially strengthen the bridge: in
VitalDB, recompute the *plain* whole-case median dose/kg (no MAP band, no stable
epochs) and show it correlates highly with the stable-epoch phenotype (the ledger
already hints at this: peak / time-weighted-mean dose correlates 0.90 with the
stable-epoch phenotype). If the plain VitalDB metric ~= the fancy one ~= the MIMIC
metric, the analogy tightens into something closer to a true replication. **This
correlation should be computed and reported; right now the cross-cohort identity
is asserted, and the in-VitalDB equivalence is stated for peak/TWM but the exact
"MIMIC-style plain median" was not shown to match.**

### A.2 The control-theory PREMISE is verified in VitalDB only; in MIMIC it is
ASSERTED, NOT SHOWN. (CONFIRMED HOLE.)

The premise is: *intraoperative MAP is feedback-regulated to target, so the
hemodynamic insult is carried by the dose, not the (held-normal) pressure.* In
VitalDB this is a measured structural fact: within-patient MAP CV 0.095 vs dose CV
0.493 (ratio 5.2) — `pressor_requirement.py` computes both because MAP is pulled
per epoch.

In MIMIC, **MAP is never pulled.** Verified by grep across all `analysis/mimic_*.py`:
the only "MAP" token is `CAREUNIT_MAP`, a Python dict in `mimic_subgroups.py`. No
chartevents, no arterial-line, no mean-arterial-pressure item is read anywhere in
the MIMIC pipeline. Therefore:
- The MIMIC requirement is **not MAP-conditioned** (you cannot condition on a
  variable you never loaded).
- The claim that "MAP is regulated so the dose carries the signal" is **not tested
  in the ICU**, where titration practice, MAP targets, and the degree of feedback
  regulation differ from the OR (different clinicians, sedation, sicker patients,
  permissive-hypotension cultures, intermittent NIBP vs continuous A-line).

**Flag:** the control-theory mechanism — the paper's headline conceptual novelty —
is a single-cohort, single-setting (intraoperative SNUH/VitalDB) result. Its
extension to the ICU is **assumed, not demonstrated.** The MIMIC mortality result
stands on its own (dose intensity predicts death), but it does **not** corroborate
the control-theory framing. The paper must not let the large-N MIMIC numbers lend
borrowed credibility to the unverified-in-ICU mechanism. Disclosable, but it must
be disclosed explicitly; currently the framing blurs it.

### A.3 Units / normalization — a real incomparability that forbids POOLING.

- VitalDB dose = `Orchestra device RATE (mL/h) / weight`. PRESSOR_REQUIREMENT.md
  caveat is explicit: "absolute mcg/kg/min needs the per-case drug concentration
  VitalDB does not expose." So the VitalDB number is in **mL/h/kg**, an arbitrary
  device-unit scaled quantity that assumes a constant institutional norepinephrine
  concentration to be even internally comparable across cases.
- MIMIC dose = **mcg/kg/min**, a true pharmacologic rate.

These are **different physical units on different (only-assumed-constant) scales.**
Consequences:
1. **No numeric comparison is meaningful.** VitalDB median 0.163 (mL/h/kg) and
   MIMIC median 0.08 (mcg/kg/min) cannot be compared, pooled, meta-analysed, or
   put on a shared axis. The paper does not appear to pool them numerically (good),
   but any sentence implying the *magnitudes* agree would be wrong.
2. **Only scale-free statistics transfer**: within-cohort reliability, rank
   correlations (early->late, split-half Spearman), and per-SD ORs. These ARE what
   the docs report — so the cross-cohort claims are, narrowly, defensible. But this
   means the replication is necessarily limited to "the *ordering* of patients by
   dose is a reliable, predictive trait," never "the *dose itself* replicates."
3. **The VitalDB unit is itself fragile**: if institutional norepinephrine
   concentration varied across cases, even the within-VitalDB between-patient
   ranking is contaminated (a patient on a more dilute bag shows a higher mL/h for
   the same mcg/kg/min). The split-half reliability is concentration-invariant
   *within* a case, but the between-patient phenotype — the entire basis of the
   "5.6-fold spread" and all construct/outcome correlations — is **not** protected.
   This is under-disclosed relative to its importance.

**Verdict A3:** units bar numeric pooling (the docs mostly respect this) and, more
seriously, the VitalDB unit's dependence on an unverified constant-concentration
assumption weakens the *within-VitalDB* between-patient phenotype, not just the
cross-cohort comparison.

### Section A overall verdict
The two findings measure **related but non-identical constructs**: a deliberately
de-confounded MAP-conditioned controller-effort dose (VitalDB) vs a plain
whole-stay dose intensity (MIMIC). The replication is **real at the level of "dose
ordering is a reliable, early, mortality-graded patient trait" but is currently
over-stated as if the specific phenotype and its control-theory mechanism were
reproduced.** Honest reframing (two-level claim + explicit "mechanism verified
intraoperatively only" + "units forbid numeric pooling, only rank/relative
statistics transfer") fully repairs it. None of this is fatal; all of it is a
framing-honesty debt the current docs have not fully paid.

---

## B. COMPLETENESS CRITIQUE — ranked remaining holes

Severity = how a top-journal (JAMA/Anesthesiology/Crit Care Med/Lancet-resp)
reviewer would weight it. "Fatal" = can change the conclusion / block acceptance of
the headline claim. "Disclosable" = a limitation that scopes but does not void the
claim.

| # | Hole | Severity | Fatal or disclosable | Fix / disclosure |
|---|------|----------|----------------------|------------------|
| 1 | **The decisive "just-sicker" adjustment (lactate + SOFA labs) is BUILT BUT NEVER RUN.** `analysis/mimic_sofa_lactate.py` exists and is described as "the DECISIVE signal-vs-sicker test," but there is **no `mimic_sofa_lactate.json` in cache** and no MIMIC labevents download (cache has only VitalDB `labs.csv`). Every severity-adjusted MIMIC result (MIMIC_MORTALITY_SEVERITY, MIMIC_SEVERITY_SCORES) explicitly carries "labs PENDING / would attenuate further / UPPER bound." The single most important rebuttal to the single most likely reviewer attack ("norepi dose is a textbook severity marker; this is just APACHE/SOFA in disguise") is **incomplete**, and the authors' own caveats concede the OR would attenuate further with lactate. | **CRITICAL** | **Potentially conclusion-relevant, currently a hole, not yet fatal.** It becomes fatal only if running it collapses the OR toward 1. Until run, the "beyond severity" claim is unfinished. | RUN `mimic_sofa_lactate.py` to completion (download labevents lactate 50813, creatinine 50912, bilirubin 50885, platelets 51265; first-24h to avoid reverse causation). Report the fully-adjusted OR. This is the highest-value remaining computation in the entire project. If it survives, the headline hardens dramatically; if it collapses, the paper's central "carries information beyond severity" claim must be retracted to "is a strong severity marker." Do NOT publish the "beyond severity" claim while this is PENDING. |
| 2 | **No pre-registration; sequential adaptive search across a now-large MIMIC test set (researcher degrees of freedom / multiplicity).** FINDINGS_LEDGER concedes "No pre-registration; the search was sequential and adaptive." The Bonferroni statement covers ~30 VitalDB tests, but the MIMIC side has since accumulated many more tests (5 severity specs, 13 subgroups, 3 mortality horizons, 5 dose formulations, 2 bedside thresholds, escalation/slope models). The "one primary claim survives Bonferroni" framing predates this expansion and was never updated to cover the MIMIC multiplicity. | **MODERATE** (borders CRITICAL for a confirmatory journal) | **Disclosable**, but only if framed as exploratory/hypothesis-generating throughout — which conflicts with the confident "SURVIVES" language. | Pick ONE pre-specified MIMIC primary (reliability + early->late + severity-adjusted OR), label everything else explicitly secondary/exploratory, and either (a) report a multiplicity correction over the FULL current test count or (b) state plainly that the MIMIC analyses are exploratory corroboration. Best fix: an actual pre-registered prospective analysis. The effect sizes (early->late 0.62, OR 3) are large enough that honest multiplicity disclosure does not threaten them — so this is fixable by framing. |
| 3 | **Selection: arterial-line / already-on-pressor population in BOTH cohorts — the denominator is sick by construction.** VitalDB requires stable A-line epochs (ledger: analyzable cohort adverse-outcome 0.71 vs 0.50 excluded). MIMIC requires a kg-normalised norepinephrine infusion (you are already on a pressor titrated by weight). The signal is only defined in patients who already declared themselves. Generalisation to "all-comers" or to a *decision at the moment you'd start a pressor* is unproven. | **MODERATE** | **Disclosable** (it scopes the claim, doesn't void it) — already partly disclosed. | Keep the scope explicit in the abstract ("in patients already receiving a weight-based norepinephrine infusion"). Do not let "early identification" drift toward "screening tool for the general OR/ICU population." |
| 4 | **"Early identification" has NO demonstrated decision benefit — and the docs already concede the null.** Decision-benefit RD is null and attenuates with N (CONCORDANCE/attack #8). The early-warning doc shows AUC and a bedside rule but explicitly: "identifies WHO is high-risk early, not that acting on the dose changes outcome." A clinical reviewer's first question on any "early-warning / actionable" framing is "actionable how — what do I DO differently, and does it help?" Answer: unknown. | **MODERATE** | **Disclosable IF the actionability language is dropped**; **fatal to the "actionable early-warning" claim specifically.** | Excise "actionable" from the early-warning claims (MIMIC_EARLY_WARNING title and verdict still say "ACTIONABLE EARLY-WARNING"). Reframe as risk-stratification / prognostic enrichment for trials, not a decision tool. The lead time (42.7 h) supports "there is a window," not "acting in the window helps." |
| 5 | **In-sample operating points / in-sample thresholds.** The bedside rule (early-peak >= 0.2 / 0.3 mcg/kg/min) and the VitalDB high-requirement threshold (0.2164) are evaluated on the same data they were chosen on. MIMIC_EARLY_WARNING discloses this ("IN-SAMPLE ... optimistic vs held-out"). The VitalDB AUC 0.771 operating point similarly lacks a held-out test. | **MINOR** | **Disclosable** (already disclosed for MIMIC; ensure VitalDB carries the same caveat). | Report sens/spec/PPV/NPV on a held-out split (MIMIC is large enough for a clean train/test). The AUCs are rank-based and honest; only the chosen-threshold operating points are optimistic. Cheap to fix in MIMIC given n=15,949. |
| 6 | **dod long-term-mortality validity (date-shift + horizon censoring).** 28d/90d/1y ORs use `(dod - intime).days`. The per-subject date shift cancels in the difference (valid), but MIMIC-IV `dod` is curated only to a limited post-discharge horizon, so beyond-horizon deaths are censored as alive. Docs disclose this and argue the *ordering* is robust (non-differential by dose). The 1y absolute rate (0.482) is a lower bound. | **MINOR** | **Disclosable** (already disclosed and the non-differential argument is sound). | Keep the lower-bound framing; optionally restrict to subjects with adequate follow-up window, or present in-hospital death (uncensored) as the primary and long-term as supportive. The monotone dose-response on in-hospital death (Q1 0.14 -> Q4 0.65) is the cleaner, censoring-free headline. |
| 7 | **ICU-LOS used as a severity covariate is a COLLIDER / mediator.** `mimic_severity_scores` adjusts mortality for ICU LOS. LOS is downstream of illness severity AND truncated by death (survivors stay longer; deaths leave early). Conditioning on LOS can bias the requirement->death estimate in either direction and is not a clean severity control. | **MINOR-MODERATE** | **Disclosable** (and easily remediated). | Drop ICU-LOS from the adjustment set (it is post-baseline). Use only baseline severity (age, comorbidity, first-24h labs, baseline #pressors). The lactate+SOFA model (#1) is the correct adjustment; LOS should not be in it. |
| 8 | **Mechanism is single-setting (intraoperative) — control-theory premise not shown in ICU (cross-ref A.2).** The novel framing rests entirely on VitalDB. | **MODERATE** (for the *mechanism* claim) | **Disclosable.** | Scope the control-theory claim to the intraoperative setting; present MIMIC as evidence the *dose summary* generalises, explicitly NOT the mechanism. |
| 9 | **Vasoplegia construct is not established (already retracted to "requirement").** SVR anchor wrong-signed at n=15; convergent tone near-null; mixed preload+tone. | **MINOR** (already handled) | **Disclosable / resolved** — label is already "vasopressor requirement," not vasoplegia. | Maintain the relabel; ensure no residual "vasoplegia" language survives in the abstract/titles (some doc titles still say VASOPLEGIA). |
| 10 | **No causal / treatment claim is supported anywhere.** Every outcome model is observational and (at best) severity-adjusted. Confounding-by-indication is unremovable without a trial. | **MODERATE** | **Disclosable** (and consistently disclosed). | Keep all language at "marks/stratifies risk," never "causes" or "treating-to-target helps." Already done; just guard against drift. |

---

## VERDICT

**Are there CRITICAL (fatal, conclusion-changing) holes left, or only disclosable
limitations?**

**One genuinely conclusion-relevant hole remains, and it is the single most
dangerous item: Hole #1 — the decisive lactate + SOFA-lab severity adjustment in
MIMIC is built but never run.** Everything else is a disclosable limitation that a
careful, honest scoping of the claim fully neutralises. But #1 is different in kind:
it is not a framing debt, it is an **unfinished analysis whose own authors predict
will move the headline number**, attacking the project's central empirical claim
("the requirement carries mortality information BEYOND illness severity"). Until
`mimic_sofa_lactate.py` is run with real labevents:

- If the OR survives lactate+SOFA-lab adjustment -> the headline hardens and the
  paper is in strong shape (only disclosable limitations remain).
- If the OR collapses toward 1 -> the central "beyond severity" claim must be
  **retracted** to "the requirement is a strong severity marker," which is a
  materially weaker (and much less publishable) paper.

Because the outcome is unknown and the authors themselves expect attenuation, the
honest status today is: **the paper has one open CRITICAL hole (a missing decisive
computation), not yet fatal but conclusion-determining, plus a cluster of
disclosable limitations and one construct-framing debt (Section A) that is being
over-sold as a clean replication.**

**Most dangerous single item: run the MIMIC lactate+SOFA-lab adjustment before
making any "beyond severity" claim.** Second-most: stop framing MIMIC as a
replication of the *specific* VitalDB phenotype/mechanism — it replicates the
*dose-ordering trait*, not the MAP-conditioned controller-effort estimand or the
control-theory premise (which is verified intraoperatively only and uses
non-comparable units).

The rest is a strong, defensible **risk-stratification / characterization** paper,
provided the actionability language (#4), the in-sample thresholds (#5), the LOS
collider (#7), and the multiplicity/pre-registration posture (#2) are disclosed and
scoped honestly — all of which the existing red-team docs are already most of the
way toward doing.

_Reviewer note: Section A findings are read directly off `pressor_requirement.py`
and `mimic_external_validation.py`; the MAP-absence in MIMIC and the missing
`mimic_sofa_lactate.json` were verified against the codebase and cache, not taken
from the prose._
