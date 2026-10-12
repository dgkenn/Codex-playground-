# REDTEAM R4 CRUX — Collapse Attempt on the At-Target Finding

**Reviewer posture:** the most dangerous collapse. Try to reduce the finding to
(a) dose→mortality (known VIS/VDI literature) plus (b) the MAP restriction-of-range
tautology. If it collapses, say so.

**Code:** `analysis/redteam_r4_probe.py` (scratchpad) — ran python3 on MIMIC landmark
cohort (n=23,920 stays, n=7,841 at-target, n=16,079 not-at-target). All AUCs are
5-fold out-of-fold logistic; confirmed against rank-based (Wilcoxon) AUC.

---

## The Collapse Thesis

> "This is nothing but (a) dose→mortality, which is the known VIS literature, plus
> (b) the tautology that MAP cannot discriminate within a narrow MAP band
> (restriction-of-range). The 'at-target conditioning' adds no new information."

---

## Test 1: Three Requirement AUCs

**If the requirement AUC is flat (~0.72–0.74 everywhere), the at-target presentation
adds no discriminative information. Only MAP's drop creates the 'gap,' making the
gap-widening a restriction artifact.**

| Stratum | n | Mortality | REQ AUC | MAP AUC | GAP |
|---|---|---|---|---|---|
| Full cohort | 23,920 | 16.0% | **0.723** | 0.558 | 0.165 |
| NOT-at-target | 16,079 | 17.8% | **0.712** | 0.555 | 0.156 |
| AT-target | 7,841 | 12.4% | **0.743** | 0.475 | 0.268 |

**The requirement AUC is NOT flat.** It ranges 0.712→0.743 across strata — the
at-target AUC is modestly but significantly higher than the not-at-target AUC
(delta = +0.031, bootstrap 95% CI [+0.012, +0.051], **does not contain zero**).

However, 0.712→0.743 are both within the VIS literature expectation (0.70–0.76 for
dose→ICU mortality). The at-target AUC is not fundamentally special in absolute terms.

**Verdict on Test 1:** Partial collapse. The requirement discriminates slightly better
at target than outside it, but the range of variation is modest, and the at-target AUC
is consistent with the known VIS dose→mortality relationship. The claim that "the
at-target stratum is where the dose signal is strongest" is true but the effect size
(+0.031 AUC) is small.

---

## Test 2: Gap Decomposition — Quantifying Each Component

**The reported finding is that the requirement-vs-MAP AUC gap nearly doubles
(0.156→0.268). How much of this is (A) MAP restriction-of-range vs (B) genuine
requirement signal gain?**

```
Gap NOT-AT-TARGET:  0.156
Gap AT-TARGET:      0.268
Total gap widening: 0.111

Component A — MAP AUC drop (restriction-of-range):
  MAP AUC not-at-target: 0.555
  MAP AUC at-target:     0.475
  MAP AUC drop:          0.080  →  72% of gap widening

Component B — REQ AUC rise (genuine signal gain):
  REQ AUC not-at-target: 0.712
  REQ AUC at-target:     0.743
  REQ AUC rise:          0.031  →  28% of gap widening

MAP SD: 9.1 (not-at-target) → 4.0 (at-target), variance ratio 0.20
```

**The collapsers are 72% correct.** The headline "gap doubles" is dominated by MAP
becoming uninformative by construction once we restrict to the narrow [65, 85] band.
This is a restriction-of-range artifact — not a finding. The MAP AUC at target
(0.475, corresponding to effective AUC ≈ 0.500 after correcting for sign) confirms
MAP is essentially random within the at-target band.

The remaining 28% (REQ AUC rise of 0.031) is a real, statistically significant
elevation. But it is modest.

**Verdict on Test 2:** The "gap doubling" framing is misleading. 72% of the
gap widening is MAP restriction, a predictable statistical artifact, not a clinical
discovery. The honest framing must say "the gap widens mainly because MAP becomes
uninformative by construction." The requirement AUC rise is real but small.

---

## Test 3: Does the At-Target Presentation Add Anything a Clinician Doesn't Already
Get from the Dose Alone?

**The VIS-collapse steelman:** The requirement IS a VIS-like quantity. Drawing the
dose–mortality curve inside the normal-MAP subgroup is: (i) observationally
confounded by severity-within-stratum (high-dose at normal MAP = vasoplegic sepsis),
and (ii) already shown by VDI/BPRI which track dose ÷ MAP or dose trajectory.

**Severity check (the confounding-by-indication test):**

| | AT-TARGET | NOT-AT-TARGET |
|---|---|---|
| Mean age | 63.0 | 66.6 |
| Mean lactate | 3.16 (n=2,590) | 3.17 (n=4,862) |
| Median NEE load | 31.3 | 49.0 |

At-target patients are **younger, on lower doses, and have identical lactate** compared
to not-at-target. This means confounding-by-indication within the at-target stratum is
not obviously worse than outside it. The high-requirement, at-target patients who die
are not simply the sickest-by-lactate patients; they carry excess mortality over and
above lactate (MICE-adjusted OR 2.04 [1.85, 2.24]).

**Age-stratified REQ AUC within the at-target stratum:**

| Age tertile | n | Mortality | REQ AUC |
|---|---|---|---|
| age < 33rd pct (< ~56y) | 2,439 | 10.2% | 0.743 |
| age 33–67th pct | 2,655 | 10.7% | 0.756 |
| age > 67th pct (> ~72y) | 2,747 | 16.0% | 0.743 |

The requirement AUC is **remarkably stable across age tertiles** (0.743–0.756). This
argues against severity (age) as the main driver. The requirement stratifies mortality
independently within each age band.

**The steelman survives partially:** within the at-target stratum, high requirement
is a severity proxy (vasoplegic sepsis). The MICE OR 2.04 is impressively robust to
adjustment, but the E-value of 2.53 means an unmeasured confounder with OR ~2.5
(e.g., shock etiology, GCS, PaO2/FiO2) could explain residual association. This
is a standard observational limitation, not specific to the at-target conditioning.

---

## Test 4: The Irreducible Novel Claim — What (If Anything) Survives?

### What is NOT novel (collapses to VIS/tautology):

1. **Dose predicts mortality (AUC 0.72–0.74):** This is precisely the VIS literature.
   The at-target requirement AUC 0.743 is fully within VIS-expectation. No new finding.

2. **The MAP restriction component of the gap (72%):** Tautological. If you restrict
   a continuous predictor to a narrow range, its AUC approaches 0.50. This is a
   statistical identity, not a clinical observation.

3. **The quartile gradient (3.1%→27.8%):** This is the dose–response curve applied to
   the at-target subgroup. VDI and BPRI already report this gradient at the full-cohort
   level. The subgroup presentation is familiar; the absolute numbers vary.

### What partially survives:

**The REQ AUC rise (+0.031, CI [+0.012, +0.051]) is real and statistically distinct
from zero.** The requirement is modestly MORE discriminating inside the normal-MAP band
than outside it. This is a small empirical fact that the restriction-of-range argument
does not explain.

**Mechanistic interpretation (honest, not proven):** Within the at-target band, MAP
variation is minimal (SD 4.0 vs 9.1), so MAP noise is suppressed and the dose signal
faces less "competition" from MAP as a competing predictor. Whether this constitutes
a genuine biological insight ("the dose is the true driver and MAP is the regulated
surrogate") or is merely a statistical property of conditioning on a near-constant is
not empirically distinguishable with observational data.

**The across-stratum gap framing itself** — comparing the information gap in two strata
— is not standard in VIS/VDI papers, which do not stratify by at-target status.
This framing is new but is partly an artifact (72% restriction).

### The irreducible finding (honest tier):

**Within ICU patients who have achieved MAP target (a post-treatment, hemodynamically
"managed" appearance), the vasopressor requirement remains a strong mortality
discriminator (AUC 0.743, 9× quartile gradient), carrying information that MAP itself
cannot provide (MAP AUC ≈ 0.50 in this stratum). The requirement's discriminative
power is modestly but significantly higher here than outside the normal-MAP band
(+0.031 AUC, p < 0.05).**

This is an incremental empirical finding, not a paradigm shift.

---

## Collapse Verdict

| Claim | Verdict |
|---|---|
| "Dose predicts mortality" | COLLAPSES to VIS literature (AUC 0.72–0.74, within expectation) |
| "Gap doubles" | LARGELY COLLAPSES: 72% is MAP restriction-of-range |
| "At-target conditioning adds information" | PARTIALLY SURVIVES: REQ AUC is modestly higher (BUT within VIS range) |
| "9× gradient is novel" | PARTIALLY COLLAPSES: gradient is the dose-response curve in a subgroup; known shape |
| "MAP is uninformative at target" | SURVIVES but is TAUTOLOGICAL: MAP AUC = 0.50 in a [65,85] band by construction |
| "Requirement stratifies when MAP cannot" | SURVIVES as a descriptive fact, NOT mechanistic proof |

**Overall:** The finding does **not completely collapse**, but the "gap doubles" framing
is misleading and must be retired. The honest irreducible contribution is modest:
within the normal-MAP ICU population, the vasopressor dose discriminates mortality
(AUC 0.74, stable across age tertiles, robust to MICE imputation). This is real,
clinically relevant, and incrementally novel relative to VIS/VDI (which do not report
at-target-conditioned AUC). It is **NOT a major novel finding** in isolation; its
value is as a subgroup-specific monitoring insight.

### Recommended tier revision:

The finding warrants **Critical Care Medicine / Intensive Care Medicine (secondary
analysis, supporting table)** — not a standalone manuscript. The at-target AUC table
belongs in a paper whose primary hypothesis is the dose–severity relationship, with
the at-target stratum as a pre-specified sensitivity analysis.

### Required reframing for intellectual honesty:

1. Replace "gap nearly doubles" with "72% of the gap widening is MAP
   restriction-of-range; the requirement AUC rises a modest but statistically
   significant 0.031 within the normal-MAP stratum."
2. State explicitly: the at-target conditioning is post-treatment; this is an
   informative subgroup presentation, not causal conditioning.
3. The primary novel quantity is the **requirement AUC within the at-target stratum**
   (0.743), not the gap itself. Frame as: "Among patients whose MAP is regulated to
   target, the dose alone discriminates mortality with AUC 0.74 — suggesting that
   monitoring the dose is necessary even when the pressure looks normal."
4. Cite VDI (Miyamoto 2025) and BPRI (Shen 2026) prominently; be explicit that the
   at-target subgroup analysis is the incremental contribution, not the dose→mortality
   signal itself.

---

*Red-team probe: `/tmp/claude-0/.../scratchpad/redteam_r4_probe.py` and `redteam_r4_part2.py`
 Run: `MIMIC_RAW=$SP MAP_RAW_DIR=$SP python3 redteam_r4_part2.py`
 Data: MIMIC-IV, landmark cohort n=23,920, at-target n=7,841. Date: 2026-06-30.*
