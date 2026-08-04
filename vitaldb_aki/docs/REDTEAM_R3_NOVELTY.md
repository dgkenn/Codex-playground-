# REDTEAM_R3_NOVELTY.md
# Role: Content Reviewer + Anesthesiology/Critical-Care Medicine Handling Editor
# Claim: "At-target MAP, vasopressor REQUIREMENT strongly stratifies mortality (Q1 3.1% vs Q4 27.8%,
#         OR ~2.6-2.8); MAP within the at-target band carries no information (AUC 0.47 vs 0.74)."
# Date: 2026-06-30
# Source: docs/ICU_OCCULT_DEPENDENCE.md; PubMed searches conducted 2026-06-30.

---

## EXECUTIVE VERDICT (for the editor)

The at-target-MAP conditioning is the paper's single differentiating move relative to all prior art.
No prior paper found restricts its analysis to the at-target stratum and then shows requirement AUC >>
MAP AUC within that stratum. That specific empirical structure is new. However, several bodies of
prior art come close enough to create serious reviewer concerns:

1. The vasopressor dependency index (VDI = dose/MAP ratio) exists as a named clinical construct used in
   Japanese ICU literature and is already applied as a hemodynamic response metric in prospective studies.
2. The Blood Pressure Response Index (BPRI = MAP/VIS) trajectory phenotyping paper (Shen et al., Critical
   Care 2026) uses essentially the same ratio in MIMIC-IV + eICU and identifies six mortality-graded
   hemodynamic phenotypes — published three months before the current claim's write-up date.
3. The SEPSISPAM trial (Asfar et al., NEJM 2014) already tested high vs. low MAP targets in septic shock
   (MAP 80-85 vs. 65-70 mm Hg) and found no mortality difference — implicitly acknowledging that MAP
   within a treated range is not the determinative variable. The norepinephrine dose required to achieve
   those targets varied and is reported, though not foregrounded as the prognostic variable.
4. High-dose norepinephrine dependency as a mortality marker (Calabro et al., J Anesth Analg Crit Care
   2026; Roberts et al., Crit Care Med 2020; EMPRESS trial protocol, Scand J Trauma 2026) is an active,
   explicitly-named clinical concern driving current RCTs.

**Net novelty verdict: PARTIALLY NOVEL. The at-target conditioning + within-band AUC contrast is new.
The concept that high vasopressor requirement at controlled MAP signals risk is not new — it is implicit
in VDI, BPRI, and the entire "vasopressor-dependent septic shock" trial space. The paper's contribution
is making the conditioning explicit, quantifying the within-band information gap, and doing so in a
large, landmark-design ICU cohort. This is publishable novelty for Crit Care Med / Intensive Care Med;
it is arguable (but possible) novelty for Anesthesiology or JAMA/NEJM-tier without a much sharper
framing.**

---

## 1. PRIOR ART / NOVELTY — DETAILED FINDINGS

### 1A. The "vasopressor dependency index" (VDI) — CLOSEST PRIOR ART, NOT NAMED IN DOSSIER

Based on articles retrieved from PubMed, the concept of the VDI (variously defined as dose/MAP or
MAP/dose ratio) is already an active clinical construct in Japanese ICU literature. Miyamoto et al.
(Shock 2025; [DOI](https://doi.org/10.1097/SHK.0000000000002654)) use a "modified vasopressor dependency
index = vasopressor dosage divided by mean arterial pressure" as the primary hemodynamic response metric
in the BEAT-SHOCK prospective registry (n=309 patients with septic shock requiring high-dose
norepinephrine). In that paper:

- Hemodynamic response was defined as ≥20% improvement in VDI within 6 h of PMX-HP.
- 28-day mortality: 8% in responders vs. 31% in nonresponders (P=0.0042).
- Key enrollment criterion: high-dose vasopressor dependency.

**This VDI paper is a direct prior-art hit.** It names and quantifies the dose/MAP ratio as a
prognostic metric in septic shock, in the ICU, with mortality as the outcome. The current claim's
denominator IS MAP; the VDI's denominator is MAP. The papers are measuring the same thing under
different names. The critical distinction the current paper can claim: it restricts to patients
ALREADY at target MAP (the at-target stratum) and shows that within that stratum, the requirement
continues to stratify mortality while MAP does not. The VDI papers do not apply this conditioning —
they include all vasopressor-on patients regardless of whether MAP is controlled.

**Severity for novelty: HIGH. The VDI must be named and distinguished explicitly, or the paper will
receive this prior-art objection from any reviewer familiar with Japanese septic shock literature.**

---

### 1B. Blood Pressure Response Index (BPRI) trajectory phenotyping — VERY CLOSE PRIOR ART, 2026

Based on articles retrieved from PubMed, Shen et al. (Critical Care 2026;
[DOI](https://doi.org/10.1186/s13054-026-06059-w)) define BPRI = MAP / Vasoactive-Inotropic Score,
apply latent class trajectory modelling to 4,389 MIMIC-IV septic shock patients, and find six
hemodynamic phenotypes with ICU mortality ranging from 21.9% to 54.5%. External validation in
1,240 eICU-CRD patients. After full multivariable adjustment, trajectory class C2 (non-responders)
OR 3.67 [2.76-4.86] for ICU mortality.

This is the same MIMIC-IV database, a ratio that is the inverse of VDI (MAP/VIS rather than dose/MAP),
and a mortality-graded phenotyping approach. The current claim produces a monotone 9x gradient (3.1%
to 27.8%) across NEE quartiles in the at-target stratum — comparable prognostic magnitude. The
differentiator the current paper has: (a) it conditions on at-target MAP explicitly, (b) it provides the
within-band AUC contrast (0.74 vs. 0.47), and (c) it uses a landmark design. The BPRI paper does not
restrict to the at-target MAP population.

**Severity for novelty: MODERATE-HIGH. The BPRI paper is close enough that a reviewer will ask "how
does this differ from BPRI trajectory analysis?" This must be answered in the introduction.**

---

### 1C. Norepinephrine dose and mortality in septic shock — KNOWN BODY, MULTIPLE PAPERS

Based on articles retrieved from PubMed:

- **Roberts et al., Crit Care Med 2020** ([DOI](https://doi.org/10.1097/CCM.0000000000004476)):
  Prospective multicenter cohort (n=616, 33 sites), first 24h NEE dosing intensity → 30-day mortality
  (adjusted OR 1.33 per 10 µg/min increase). This is the canonical NEE dose-response mortality paper in
  septic shock. Neither the MAP level nor at-target conditioning is the focus; the entire septic shock
  population is included. **Already identified in Round 1; remains the primary direct prior art.**

- **Calabro et al., J Anesth Analg Crit Care 2026**
  ([DOI](https://doi.org/10.1186/s44158-026-00425-4)): Retrospective cohort (n=506 septic shock
  patients, 2016-2022), NE peak-dose ranges → stepwise ICU mortality from 20.7% (lowest dose group)
  to 100% (>3.0 µg/kg·min group); AUROC 0.75 for ICU mortality; adjusted OR 2.55 for the 1.2-3.0
  group. **Published June 2026, not in prior dossier. This is a direct competitor.**

- **EMPRESS trial protocol (Luo et al., Scand J Trauma 2026)**
  ([DOI](https://doi.org/10.1186/s13049-026-01563-y)): An active multicenter RCT for "high-dose
  vasopressor-dependent septic shock" (NEE >0.3 µg/kg/min within 24h) treating it as a named,
  clinically recognized subpopulation. The existence of this trial confirms the clinical concept of
  vasopressor dependency as a real phenotype recognized by the CCM community.

**Severity for novelty: HIGH for Calabro 2026 (not in dossier, very similar result). CRITICAL for
Roberts 2020 (already flagged, must be front-and-center in the introduction as the prior art paper
that the at-target conditioning extends and differentiates from).**

---

### 1D. The MAP-target trials — SEPSISPAM, 65-TRIAL, OVATION, OPTPRESS

Based on articles retrieved from PubMed:

- **Asfar et al. (SEPSISPAM), NEJM 2014** ([DOI](https://doi.org/10.1056/NEJMoa1312173)): n=776 septic
  shock patients, MAP target 80-85 vs. 65-70 mm Hg, no mortality difference at 28 or 90 days. Within
  each arm, patients were treated with vasopressors to hit the MAP target; the dose required to hold
  that target varied but was not used as the primary or secondary comparator endpoint. The trial
  implicitly demonstrates that "which MAP target" does not determine mortality, but never shows that
  "how much vasopressor to hold a given MAP" predicts mortality within the at-target population.

- **OPTPRESS trial (Endo et al., Intensive Care Med 2025)**
  ([DOI](https://doi.org/10.1007/s00134-025-07910-4)): n=518 older Japanese patients, MAP 80-85 vs.
  65-70 mm Hg target; trial terminated early for harm (39.3% vs. 28.6% 90-day mortality in high-target
  group). Again, vasopressor dose required to hit the target was higher in the high-MAP arm but was not
  analyzed as the informative variable within the at-target stratum.

These MAP-target trials are relevant for context but do not perform the at-target conditioning analysis.
They show that targeting a higher MAP increases vasopressor requirements and (in older patients) harm —
but they do not ask "among patients who achieved the target, does dose predict who dies?" The current
claim asks and answers exactly that question. This is a genuine gap in the MAP-target literature.

**Severity for novelty: LOW-MODERATE. The gap is real. The MAP trials provide supporting context and
the framing that MAP targets per se do not determine mortality, which the current claim mechanistically
extends by showing dose within the target does.**

---

### 1E. The "occult hypoperfusion at normal blood pressure" literature

A PubMed search for "occult hypoperfusion normal blood pressure vasopressor ICU mortality" returned
zero results under that combined search, and targeted searches for the concept found it primarily in
the trauma/resuscitation context (cryptic shock, lactate elevation with normal BP) rather than in the
ICU vasopressor-titration context. The concept that a patient can have adequate MAP but inadequate
tissue perfusion is established (cryptic shock, microcirculatory decoupling), but the specific form
"adequate MAP maintained by high vasopressor → occult risk" is not a named construct in the ICU
literature found by these searches. It is distinct from cryptic shock (which refers to low MAP or low
flow despite apparently adequate resuscitation), and the current claim is not citing that literature
anyway.

**This is the framing element with the highest novelty. The "monitoring-error" angle — the MAP number
on the monitor is falsely reassuring because it is the controlled variable, not the informative one —
has not been formally demonstrated in a large at-target-only cohort with outcome data.**

---

### 1F. Nishikimi et al. (Critical Care 2026) — dose-MAP response dynamics

Based on articles retrieved from PubMed, Nishikimi et al. (Critical Care 2026;
[DOI](https://doi.org/10.1186/s13054-026-05920-2)) studied minute-by-minute MAP response to
different initial NE doses in 5,349 ICU patients with hypotension. Failure to achieve MAP ≥65 mm Hg
within 60 min was independently associated with ICU mortality (OR 1.49 [1.27-1.76]). This paper
studies the dynamics of getting to target, not what happens to risk after the target is achieved.
It does not perform at-target-only conditioning. Not a direct prior-art threat, but should be cited
as context for the MAP-response physiology.

---

## 2. NOVELTY MATRIX — WHAT IS NEW VS. KNOWN

| Element | Status | Notes |
|---|---|---|
| NEE/vasopressor dose → ICU mortality, dose-response | KNOWN | Roberts 2020 (prospective, n=616); Calabro 2026 (n=506); VIS meta-analysis 2024 |
| "Vasopressor dependency" as a named clinical phenotype | KNOWN | EMPRESS trial, BEAT-SHOCK registry, high-dose NE as eligibility criterion in RCTs |
| VDI (dose/MAP ratio) predicting mortality in septic shock | KNOWN | Miyamoto/BEAT-SHOCK 2025 — direct prior art using the same ratio |
| BPRI (MAP/VIS ratio) trajectory phenotyping, MIMIC-IV | KNOWN | Shen et al., Critical Care 2026 — same database, similar construct |
| MAP target level does not determine mortality | KNOWN | SEPSISPAM 2014, 65-trial, OPTPRESS 2025 |
| **At-target-MAP stratum conditioning as the analysis frame** | **NEW** | No prior paper restricts to at-target patients and contrasts requirement vs. MAP |
| **Within-band AUC contrast: requirement AUC 0.74 vs. MAP AUC 0.47** | **NEW** | The information-theoretic comparison at equal MAP levels is new |
| **Monotone 9x mortality gradient within a normally-mapped population** | **NEW** | Q1 3.1% to Q4 27.8% — the range while MAP is "normal" is striking and unreported |
| **Control-theory premise confirmed in ICU (MAP CV 0.125 vs. dose CV 0.440)** | **NEW in ICU** | VitalDB showed intraop version; MIMIC-IV confirmation is new |
| **Landmark design (alive at 24h → subsequent death) at scale (n=7,841)** | **NEW in design** | Roberts 2020 is contemporaneous; no prior paper uses landmark within at-target stratum |
| "Monitoring error" framing (MAP is falsely reassuring) | PARTIALLY NEW | Concept is in clinical intuition; explicit quantification with AUC at at-target band is new |

---

## 3. CLINICAL IMPORTANCE / ACTIONABILITY — "MONITORING-ERROR" FRAMING

### 3A. Is the framing clinically resonant?

YES, and strongly so in the ICU context. The monitoring-error angle is the kind of finding that
clinicians immediately recognize as important because it names a cognitive error they make daily:
"the MAP is 75, we're fine." The data says: at MAP 75, if it took 0.05 µg/kg/min to get there,
mortality is 3%; if it took 0.5 µg/kg/min, mortality is 28%. That delta — both patients with the same
number on the monitor — is the clinical punch. This is not a known intuition that has been formally
quantified at scale with a landmark design and an AUC comparison.

The framing is actionable in one concrete sense: a clinician looking at a patient with "normal MAP" can
now ask "how much vasopressor did it take to get here?" and use that as a risk-stratification tool.
For ICU nurses and residents, this reframes the bedside task: note the dose required to maintain MAP,
not just whether MAP is normal. This is a teaching point, a monitoring standard, and a rationale for
risk-adjusted conversations with families.

### 3B. Is it Anesthesiology/CCM-tier or just formalizing known clinical intuition?

The ICU clinician's intuition that "a patient on 0.5 µg/kg/min of norepinephrine with a normal MAP is
sicker than one on 0.05 µg/kg/min" exists and is real. What the literature has NOT done is:

(a) Quantify it at scale within the at-target stratum (the conditioning is what eliminates the obvious
    confound that sicker patients also have lower MAP),
(b) Show that within this stratum MAP carries near-zero information (AUC 0.47), while requirement
    carries strong information (AUC 0.74),
(c) Demonstrate a 9x mortality gradient within a population that the monitor classifies as "at goal."

These three elements together constitute the kind of formal demonstration that converts clinical
intuition into a citable finding that can change monitoring practice. This is CCM-tier territory.
For Anesthesiology, the framing fits only if the broader paper also includes an intraoperative arm
(which the INSPIRE analysis showed does not support the claim in elective surgery) — the pure ICU
version belongs in Critical Care Medicine, Intensive Care Medicine, or CHEST.

### 3C. Actionability gap and the honest answer

Unlike the perioperative "trait" paper, this finding has a direct actionable implication: when you
report vasopressor use, report the dose relative to the MAP achieved, not just the MAP or just the
dose. The existing monitoring paradigm (MAP alarms, MAP targets) is incomplete. The complete signal
is: (MAP, dose to maintain MAP). This is actionable at the bedside NOW without new technology —
it requires only reading two numbers instead of one.

The paper does not need to prescribe an intervention. The finding stands as a monitoring-standard
recommendation: "In ICU patients receiving vasopressor support, the dose required to maintain
target MAP should be documented and communicated as a risk signal, even when MAP is at goal."
This is CCM/ICM-publishable on its own terms.

---

## 4. THE MAP RESTRICTION-OF-RANGE CAVEAT — DOES IT SINK THE HEADLINE?

### 4A. The methodological concern

The claim "MAP carries no information within the at-target band (AUC 0.47)" is mathematically
expected: by design, MAP variance is small in the [65,85] window. A predictor forced into a narrow
range will have attenuated AUC regardless of its true prognostic capacity. This is the classic
restriction-of-range artifact. An astute reviewer will immediately note this and call the MAP AUC 0.47
result uninformative — it is (partially) an artifact of the study design, not a physiological finding.

### 4B. How much does this weaken the clinical message?

It weakens the NEGATIVE MAP claim considerably, but NOT the positive requirement claim. The paper
should be restructured so it never leads with "MAP is uninformative." The load-bearing, non-artifactual
claim is entirely on the requirement side:

- Requirement AUC 0.74 within the at-target band is NOT a restriction-of-range artifact — requirement
  is free to vary (it IS varying: the whole point is that Q1 and Q4 have very different doses).
- The 9x mortality gradient (3.1% to 27.8%) across NEE quartiles within the normal-MAP population is
  not an artifact — it is a direct observation.
- The age-adjusted OR 2.82 and age+lactate OR 2.59 are real effect sizes that survive adjustment.

### 4C. The correct framing

The paper should NOT claim "MAP is uninformative at normal blood pressure." It should claim:

"Within the population of ICU patients whose MAP is at target — a population that monitoring tools
currently classify as hemodynamically managed — the vasopressor requirement stratifies mortality
(AUC 0.74, OR 2.82) across a 9-fold gradient, while the MAP value at which they are held provides
no additional discriminating information. The information relevant to prognosis lives in the
controller effort required to achieve the MAP goal, not in the goal itself."

This framing is (a) accurate, (b) does not overclaim on the MAP AUC artifact, (c) still carries
the clinical punch ("9x gradient in a normal-MAP population"), and (d) is logically distinct from
the VDI/BPRI prior art because it explicitly conditions on the at-target state.

**The restriction-of-range caveat, if acknowledged honestly in the paper, does not sink the clinical
message — it only limits one interpretive sentence. The paper should make this explicit in a
Limitations paragraph and then move on.**

---

## 5. RANKED CONCERNS

| Rank | Concern | Severity | Action |
|---|---|---|---|
| 1 | VDI literature not addressed: Miyamoto/BEAT-SHOCK 2025 (VDI = dose/MAP, MIMIC septic shock, mortality-graded response) is direct prior art for the ratio construct | CRITICAL | Cite, acknowledge, distinguish: VDI does not condition on at-target; at-target conditioning is the novel move |
| 2 | Shen et al. BPRI trajectory paper, Critical Care 2026 (MAP/VIS in MIMIC-IV, 6 mortality-graded phenotypes, OR up to 3.67) is same database + same ratio + same outcome | CRITICAL | Cite, acknowledge, distinguish: BPRI does not restrict to at-target MAP stratum; the within-band AUC contrast is original; landmark design is original |
| 3 | Calabro et al. 2026 (NE dose stepwise mortality, AUROC 0.75, n=506) not in dossier — directly competitive with the NEE-mortality result | CRITICAL | Add to introduction as direct prior art; the differentiator is at-target conditioning and landmark design |
| 4 | Restriction-of-range artifact for MAP AUC 0.47 — will be immediately flagged by any quantitative reviewer | HIGH | Acknowledge explicitly in Methods/Limitations; reframe so the headline rests on requirement AUC 0.74, not on MAP AUC 0.47; add supplementary analysis with MAP as continuous predictor (not just within-band variance) to show the artifact is real but bounded |
| 5 | Severity confounding: high requirement at at-target MAP may index vasoplegic/septic patients independent of the at-target conditioning | HIGH | Full SOFA score, APACHE IV, and comorbidity adjustment required for the primary result; current age+lactate model (n=2,590 complete cases) is insufficient; multiple imputation needed |
| 6 | Complete-case lactate analysis: n=2,590 of 7,841 (33%) — informative missingness (sicker patients more likely to have lactate measured, biasing toward the null or toward the positive) | HIGH | Imputation or IPCW-weighted analysis required before submission |
| 7 | "Vasopressor dependency despite adequate MAP" is a recognizable clinical concept even without prior quantification — the paper needs to own this explicitly and show the formal quantification is the contribution, not the concept itself | MODERATE | Introduction paragraph: "The clinical concern that vasopressor requirement at normal MAP signals risk is recognized but has not been formally quantified at scale or demonstrated to carry information beyond MAP itself. We provide that quantification." |
| 8 | MAP source mix (invasive ABPm + NBP fallback): the regulated-to-target claim is most physiologically valid for patients with arterial lines; NBP patients may have different MAP regulation patterns | MODERATE | Invasive-only sensitivity analysis; report n with art-line vs. NBP in Table 1 |
| 9 | At-target definition is one choice ([65,85], <10% below 65): finding may be sensitive to band width | MODERATE | Sensitivity analysis with [65,75], [65,80], [65,90] and <5% vs. <20% below 65 |
| 10 | No pre-registration for this specific analysis | LOW | Disclose; note the analysis follows from the pre-specified control-theory hypothesis; Bonferroni for multiple outcomes |

---

## 6. TARGET JOURNAL + TIER ASSESSMENT

### Realistic tier

| Journal | Verdict | Rationale |
|---|---|---|
| Critical Care Medicine (CCM) | YES — strong fit | Direct ICU mortality finding, MIMIC-IV data, n=7,841, landmark design, monitoring-error framing. CCM publishes exactly this type of large EHR-based, control-theory-motivated finding. The VDI/BPRI prior art is close enough to require careful differentiation but not close enough to block. |
| Intensive Care Medicine (ICM) | YES — strong fit | European flagship, similar scope and rigor; the at-target conditioning is the kind of nuanced methodological move ICM appreciates. |
| CHEST | YES — reasonable fit | Strong clinical message, large n, but less methods-forward than CCM/ICM. |
| JAMA / NEJM / Lancet | NO | No RCT, no intervention. Observational finding in MIMIC (a dataset editors see constantly) without a prospective validation or clinical trial hook. The 9x gradient is striking but not a practice-changing RCT result. |
| Anesthesiology | ONLY WITH INTRAOP ARM | The pure ICU finding without an intraoperative arm or perioperative context belongs in CCM, not Anesthesiology. If the paper were primarily the perioperative trait finding AND included this ICU finding as confirmatory extension, Anesthesiology remains viable. As a standalone ICU-only paper, Anesthesiology will return it: "out of scope." |

**Recommended primary target: Critical Care Medicine.**
**Recommended secondary target: Intensive Care Medicine.**
**Avoid: Anesthesiology for this specific analysis as a standalone paper.**

---

## 7. SINGLE BIGGEST DESK-REJECT RISK

> **The paper will be desk-rejected at any CCM-tier journal if it fails to address the VDI and BPRI
> literature explicitly and upfront. A reviewer familiar with the BEAT-SHOCK registry or the Shen et al.
> BPRI Critical Care 2026 paper will correctly observe that the dose/MAP ratio in ICU septic shock
> mortality has already been explored in MIMIC-IV, and will reject unless the at-target conditioning and
> within-band AUC contrast are immediately and clearly positioned as the new contribution relative to
> those prior papers.**

---

## 8. THE SINGLE BEST FRAMING THAT MAXIMIZES TIER

**Frame: "The Vasopressor Requirement at Target MAP: a large-cohort demonstration that normal blood
pressure conceals a 9-fold mortality gradient defined by the dose required to hold it."**

The framing has three load-bearing sentences:

1. "Among 7,841 ICU patients whose MAP was maintained at target for the first 24 hours, the
   norepinephrine-equivalent load required to hold that pressure stratified post-24h mortality from
   3.1% in the lowest requirement quartile to 27.8% in the highest (age-adjusted OR 2.82 [2.58, 3.09])."

2. "Within this at-target population, the MAP value itself carried near-zero discriminating information
   (AUC 0.47), while the vasopressor requirement carried substantial information (AUC 0.74) — a
   monitoring-error finding: the number on the monitor that signals hemodynamic control conceals the
   risk signal that lives in the effort required to achieve it."

3. "Unlike the Vasoactive-Inotropic Score, the vasopressor dependency index, and prior NEE dose-response
   analyses, this finding is conditional on MAP being at target — the population in which clinicians are
   MOST likely to be falsely reassured by the blood pressure value."

This framing (a) names the prior art and immediately differentiates, (b) leads with the clinical
finding (9x gradient), not the statistical construct (AUC), (c) the monitoring-error metaphor is
memorable and editorial-page-worthy, and (d) the at-target conditioning is the differentiating move
stated in the first 30 words of the abstract.

---

## 9. PRIOR ART VERDICT SUMMARY

**KNOWN (substantially pre-empted):**
- NEE dose → septic shock mortality (Roberts 2020, Calabro 2026)
- VDI (dose/MAP) as a hemodynamic response metric (BEAT-SHOCK/Miyamoto 2025)
- BPRI (MAP/VIS) trajectory phenotyping in MIMIC-IV (Shen et al., Critical Care 2026)
- "Vasopressor dependency" as a recognized clinical phenotype driving active RCTs (EMPRESS)
- MAP target level does not determine mortality (SEPSISPAM 2014, OPTPRESS 2025)

**GENUINELY NEW (what the paper uniquely contributes):**
- At-target-MAP conditioning as the analysis stratum: comparing patients who all achieved MAP goal,
  stratified only by what it cost them to get there
- Within-band AUC contrast (requirement AUC 0.74 vs. MAP AUC 0.47 within the at-target population)
- 9x mortality gradient (3.1% to 27.8%) across NEE quartiles within a "normal MAP" population
- Landmark design at scale (n=7,841) within the at-target stratum defeating reverse-causation
- Control-theory confirmation in ICU (MAP CV 0.125 vs. dose CV 0.440, MIMIC-IV, n=21,154)

**Bottom line for the editor:**
The paper's intellectual core is the at-target conditioning, not the dose-mortality association. The
dose-mortality association is known; what is new is showing it persists in the stratum where clinicians
believe the problem is solved. If the abstract leads with "vasopressor requirement predicts mortality,"
it will be desk-rejected as redundant with Roberts 2020, Calabro 2026, and the VDI literature. If it
leads with "among patients at MAP target, requirement stratifies a 9-fold mortality gradient that MAP
cannot see," it is a new finding. The desk-reject risk is entirely in the framing, not in the data.

---

*PubMed searches conducted 2026-06-30. Key new prior-art articles not in prior dossier rounds:*

- *Miyamoto et al. BEAT-SHOCK VDI 2025: [DOI](https://doi.org/10.1097/SHK.0000000000002654)*
- *Shen et al. BPRI trajectories Critical Care 2026: [DOI](https://doi.org/10.1186/s13054-026-06059-w)*
- *Calabro et al. NE dose ranges CCM 2026: [DOI](https://doi.org/10.1186/s44158-026-00425-4)*
- *Asfar et al. SEPSISPAM NEJM 2014: [DOI](https://doi.org/10.1056/NEJMoa1312173)*
- *Endo et al. OPTPRESS ICM 2025: [DOI](https://doi.org/10.1007/s00134-025-07910-4)*
- *Nishikimi et al. NE dose-MAP dynamics Critical Care 2026: [DOI](https://doi.org/10.1186/s13054-026-05920-2)*
- *EMPRESS trial protocol (Luo et al.) Scand J Trauma 2026: [DOI](https://doi.org/10.1186/s13049-026-01563-y)*
- *Roberts et al. NEE mortality Crit Care Med 2020: [DOI](https://doi.org/10.1097/CCM.0000000000004476) (prior dossier; confirmed)*
