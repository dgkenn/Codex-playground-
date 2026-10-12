# Occult Hypoxemia Propagates into Racial Misclassification of ARDS Severity and the SOFA Respiratory Score

**Status:** cycle-12 WIN (predicted HIGH → WIN). Internally hardened (subject-clustered inference survives);
novelty = NARROW-BUT-NOVEL (fills a named gap in Erlebach 2025). External validation pending eICU
`vitalPeriodic` acquisition (download launched). Realistic first-submission tier: JAMA IM / AJRCCM /
Lancet Respiratory / Crit Care Med — NEJM-adjacent, policy-timely with the 2024 Global ARDS Definition.

**One-line contribution:** using arterial-gas ground truth matched at equal *true* PaO₂/FiO₂ (PF) severity,
this is the first study to show that pulse-oximeter racial bias mechanically propagates through the
SpO₂/FiO₂ (SF) surrogate into quantified racial **misclassification** of the two formal instruments that gate
ARDS-trial enrollment, ECMO/proning escalation, and SOFA-based crisis triage — the Berlin/global ARDS
severity class and the SOFA respiratory subscore.

## Why this is the winning template (and why it beats the harm-chain ideas)

It is a **propagation-map into a decision-score**: a bias that is already externally established across many
cohorts (occult hypoxemia; Sjoding NEJM 2020, Fawzy 2022, Wong 2021, Saidy 2025) is followed arithmetically
into a formula (SF) that feeds two consequential scores. The endpoint is the **misclassification of the score
that itself drives decisions** — not a downstream hard outcome. This sidesteps the selection wall that stalled
the calcium-workup and potassium-hypoglycemia chains (see LESSONS: the paired-reference cohort cannot observe
realized harm). The score IS the action.

## Cohort (MIMIC-IV)

104,696 paired ABG↔SpO₂↔FiO₂ observations (SpO₂ ≤ 97, where the SF surrogate is valid), **10,841 Black /
93,855 White**. Itemids: SpO₂ 220277, arterial SaO₂ 220227, PaO₂ 220224, FiO₂ 223835, PEEP 220339. FiO₂
normalized to fractions; ABG↔SpO₂ paired ±30 min, FiO₂ carry-forward ≤4 h.
- PF = PaO₂/FiO₂ (truth); SF = SpO₂/FiO₂ (surrogate). ARDS-Berlin on PF (PEEP≥5): mild 200–300, moderate
  100–200, severe <100. SF cutoffs (Rice 2007): SF 315≈PF 300, SF 235≈PF 200. SOFA-resp: PF<400→1, <300→2,
  <200→3, <100→4.

## Results (all directionally as predicted; subject-clustered inference survives)

| Test | Contrast | Effect | Cluster-robust 95% CI (subject_id) | Survives |
|---|---|---|---|---|
| 1 | SF over-read at matched true PF | **Black +6.87 SF units** (naïve z=7.44); at PF 180–220 SF 215.3 vs 207.4 = **+7.9**, straddling cutoffs | — | YES |
| 2a | ARDS under-class PF<200→SF≥235 | Black 9.5% vs White 6.8%, **OR 1.43** | 1.21–1.69 (z=4.24) | YES |
| 2b/4 | ARDS under-class PF<300→SF≥315 | Black 2.5% vs White 1.2%, **OR 2.00**; attributable missed-ARDS **+1.2 pp** (CI +0.9…+1.5) | 1.56–2.55 (z=5.51) | YES |
| 3 | SOFA-resp under-score ≥1 pt | Black 9.2% vs White 5.8%, **OR 1.66** | 1.46–1.88 (z=7.81) | YES |

Clustering inflates SEs ~1.8× (patients contribute a median of 4, up to 498, pairs) but leaves ORs unchanged;
a **one-pair-per-subject** independent-observations check gives even larger point ORs (1.46 / 2.78 / 1.98). The
inference concern is fully resolved.

## Robustness (all pass)

- **FiO₂ charting confound ruled out:** mean FiO₂ 0.558 Black vs 0.556 White (identical medians).
- **SpO₂ nonlinearity ruled out:** restricting to SpO₂ 88–96 leaves Test 1 unchanged (Black +6.87, z=7.05).
- **Berlin PEEP restriction:** Test 2 holds at PEEP≥5 (OR 1.41).
- **Positive control replicates Sjoding:** occult hypoxemia (SpO₂≥92 & SaO₂<88) Black 2.43% vs White 1.18%,
  OR 2.09; mean pulse-ox bias +2.45 (Black) vs +1.51 (White).

## Honest scoping (must carry into any submission)

1. **The SOFA claim is a TAIL/threshold-crossing effect, not a population-mean shift.** Mean PF−SF is
   net-negative in *both* races (SF is globally conservative / over-scores severity — the well-documented
   curvilinear SF↔PF ceiling, Rice 2007 / Erlebach 2025). The *racial* harm lives specifically in the
   under-scoring tail (SF crossing a threshold to a milder class more often in Black patients). This framing is
   also the only one compatible with **Ashana 2021 / Miller 2021**, which found the *whole* SOFA score
   *over*-predicts mortality for Black patients on net (renal-driven, opposite direction) — must be cited and
   reconciled explicitly, not ignored.
2. **ABG-instrumented, high-acuity cohort** — generalization to non-ABG patients untested.
3. **Race is an administrative proxy for skin pigmentation** — biases the estimate toward the null
   (conservative).
4. **Internal (MIMIC) only so far** — external validation launched (eICU `vitalPeriodic`).

## Prior art and the irreducible novel contribution (novelty = NARROW-BUT-NOVEL)

- **Erlebach 2025, Crit Care (PMID 39972458)** — does the exact SF→Berlin-class misclassification analysis
  (33% misclassified) but with **no race stratification**, and explicitly states the skin-tone/race effect
  "has not been assessed." *We fill that named gap.*
- **Saidy 2025, J Intensive Care Med (PMID 40665879)** — eICU BOLD: Black race predicts SpO₂–SaO₂ discrepancy
  (aOR 1.35) and occult hypoxemia (aOR 1.22), which predict higher subsequent SOFA/mortality. Treats SOFA as a
  downstream *prognostic outcome*, not as an instrument mechanically under-scored at matched true PF. (Also
  confirms eICU HAS the SpO₂ substrate — the external-validation path.)
- **Wong/Charpignon 2021, JAMA Netw Open (PMID 34730820)** — occult hypoxemia → organ dysfunction, association
  framing, not score misclassification.
- **Gadrey 2023, Crit Care Explor (PMID 36699241)** — builds a bias-corrected respiratory measure and shows
  occult-hypoxemia-driven SOFA-**resp** under-scoring in Black patients — the CLOSEST respiratory-specific
  precedent; **must cite**. It partially pre-empts our SOFA-resp piece, but is respiratory-only and does not do
  the **ARDS-Berlin severity-class** misclassification nor the matched-true-PF test suite; our ARDS-Berlin +
  Erlebach-gap framing remains the distinct contribution. (This narrows but does not eliminate C12-1's novelty —
  scope the SOFA-resp claim as confirming/extending Gadrey with the Berlin-class propagation as the novel core.)

Irreducible contribution: **the first race-stratified quantification of SF-surrogate misclassification of the
formal ARDS-Berlin class and SOFA-resp subscore against arterial ground truth at matched true severity** —
timely because the **2024 Global ARDS Definition explicitly adopts SpO₂/FiO₂**, so this bias is about to be
institutionalized into the diagnostic criteria themselves.

## Next steps to submission-ready

1. **External validation in eICU** (Tests 1–4 by ethnicity; `vitalPeriodic` SpO₂ + `respiratoryCharting` FiO₂
   + lab PaO₂; download in progress). Saidy 2025 confirms the substrate exists.
2. **Reconcile with Ashana/Miller** (whole-SOFA opposite direction) — a short decomposition showing the
   respiratory-subscore/threshold effect coexists with the renal-driven whole-score effect.
3. Frame around the 2024 Global ARDS Definition's SpO₂/FiO₂ adoption (policy urgency).

## eICU EXTERNAL VALIDATION — the propagation does NOT replicate (major tempering)

Full eICU replication (vitalPeriodic SpO₂ + lab PaO₂/FiO₂/SaO₂ + patient ethnicity): 70,044 SF/PF pairs
(22,301 pts, 154 hospitals) + 157,079 occult-hypoxemia pairs (38,871 pts, 152 hospitals).

| Test | MIMIC | eICU | Verdict |
|---|---|---|---|
| **Positive control — occult hypoxemia** (SpO₂≥92 & SaO₂<88) | OR 2.09 | **OR 2.03 (z=8.29)**; differential bias +1.15 SpO₂ units (z=6.31) | **REPLICATES cleanly, universal** |
| Test 1 — SF over-read at matched PF | +6.87 (z=7.44) | **−3.42, model-dependent, ~0 in matched bands** | **FAILS (wrong sign)** |
| Test 2 — ARDS under-class | OR 1.43 / 2.00 | **OR 1.06 (null) / 1.29** | **attenuated/partial** |
| Test 3 — SOFA-resp under-score | OR 1.66 | **OR 1.03 (null)** | **FAILS** |

**Clean dissociation.** The occult-hypoxemia BIOMARKER bias is confirmed and universal (OR ~2, both cohorts) —
but that is essentially Sjoding's established finding. Our NOVEL contribution — the racial misclassification of
ARDS-Berlin / SOFA-resp via the SF surrogate — does **not** replicate at MIMIC magnitude. The mechanistic
sanity check exposes why: the differential bias (+1.15 SpO₂ ÷ FiO₂ ≈ **+2 SF units**) is where eICU lands, while
MIMIC's +6.87 is ~3× the mechanistic prediction → **MIMIC over-estimated the propagation.** Contributing:
eICU's very sick, left-shifted ABG cohort (median PF 160) leaves little classification headroom for SF to
under-call, and eICU FiO₂ is lab-sourced (vs MIMIC ventilator-charted).

**REVISED STANDING (honest downgrade):** C12-1 is NOT a clean externally-validated flagship. The biomarker bias
is universal (but known); the SF→ARDS/SOFA racial-misclassification propagation is **small, MIMIC-specific /
acuity-bounded, and externally unconfirmed.** Honest options: (a) publish as a *dissociation* — "occult hypoxemia
is universal, but its propagation into SF-based severity scores is acuity/cohort-dependent and does not
replicate in a sicker multi-hospital cohort" (a legitimate boundary-condition/negative contribution); (b) drop
the strong misclassification claim. Do NOT position the SF/ARDS/SOFA propagation as robust. The integrity gate
(external validation) caught an over-claim that internal cluster-robustness had passed.

## Artifacts (scratchpad, gitignored)
`oh_extract.py`, `oh_race.py`, `oh_analyze.py`, `oh_tests.py`, `oh_cluster_inference.py`,
`occult_hypoxemia_SOFA_ARDS_REPORT.md`, `occult_hypoxemia_hardening_REPORT.md`,
`occult_hypoxemia_novelty_REPORT.md`.
