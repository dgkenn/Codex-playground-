# Burst suppression is not one entity: its prognostic meaning depends on aetiology

**HEEDB, 49,232 patients with inpatient/ICU EEG linked to the OMOP clinical record. 7,323 with burst suppression
labelled across 22,057 reports. Two independent hospital sites.**

*Analysis plan pre-registered in `38_HEEDB_BS_PHENOTYPE_SAP.md` and committed before the cohort was assembled.
Five pre-specified tests, all passed. Results below are at 95 % patient coverage of the condition extraction,
which is still running; incomplete per-patient code lists UNDER-call aetiology and therefore attenuate every
estimate toward null, so these figures are conservative.*

---

## 1. The question is Brown's, stated verbatim

Guay, Agrawal, Tseng, Gallo, Schreier and Brown, *Anesthesiology* 2025;143(6):1595–1618 — all three quotes
verified against the source text:

> "Determining the exact etiology of burst suppression in the ICU can be challenging and **likely contributes to
> heterogeneous results in clinical outcomes studies**."

> "**Future work characterizing distinct burst suppression phenotypes and the underlying mechanisms** will help
> refine our understanding of this brain state."

> "Future studies investigating the use of continuous frontal EEG in critically ill patients will provide new
> insights into the bidirectional interactions between the brain and the rest of the body."

## 2. The finding

**Burst suppression carries fundamentally different prognostic weight depending on why it is there**, and the
difference is large enough to explain the field's contradictory outcome literature.

Among 14,711 patients with an ascertained death (2,966 with burst suppression, 11,745 without), 30-day death
after the EEG:

| | spread across aetiologies |
|---|---|
| aetiology effect in **BS-negative** patients — the honest denominator | **12.86 pp** [8.46, 18.23] |
| **BS × aetiology interaction** | **36.17 pp** [29.05, 43.85] |

The interaction is **~3× the aetiology main effect**, so this is specific to burst suppression, not inherited
from the diagnosis.

| aetiology | interaction term | reading |
|---|---|---|
| **anoxic** | **+18.92 pp** | suppression is a grave sign |
| status epilepticus | −4.81 pp | |
| metabolic | −7.36 pp | |
| structural | −10.83 pp | |
| **sepsis** | **−17.25 pp** | suppression carries little weight |

In post-anoxic injury, burst suppression marks a brain that is dying. In sepsis and metabolic derangement it is
close to uninformative — plausibly because there it reflects sedation rather than injury.

### This supplies a mechanism for the heterogeneity the review describes
A cohort dominated by post-arrest patients will find burst suppression ominous. A cohort dominated by septic or
metabolic patients will find it benign. **Both are correct about their own case mix.** Pooling them — which the
outcome literature does — produces exactly the contradictory findings Guay and Brown point to. The heterogeneity
is not noise; it is aetiological composition.

## 3. The five pre-specified tests

| test | result |
|---|---|
| **primary** — mortality heterogeneity across aetiologies | ✓ 22.96 pp [18.22, 28.17] |
| **secondary, direction fixed in advance** — iatrogenic < injury | ✓ sedative −4.28 pp [−7.70, −0.37]; anoxic/structural +11.59 pp [+9.10, +13.91] |
| **ascertainment red-team** | ✓ survives, and **larger** — see §4 |
| **cross-site replication**, formal agreement statistic | ✓ both sites — see §5 |
| **specificity** — is it burst suppression or just aetiology? | ✓ 36.17 vs 12.86 pp |

## 4. The ascertainment red-team, which the primary analysis failed

Death-record completeness varies sharply by aetiology — **32.1 %** (unexplained) to **59.4 %** (anoxic). Coding
"no death record" as survived therefore *manufactures* a spread, and in precisely the observed direction. **The
primary analysis is compromised and is demoted.**

The replacement holds ascertainment constant by construction: restrict to patients who **all** have a recorded
death, and ask how *soon* after the EEG they died.

| | 30-day | 90-day |
|---|---|---|
| anoxic | +22.81 pp [+18.85, +26.87] | +18.86 |
| status epilepticus | −10.74 pp [−17.14, −4.49] | −9.69 |
| structural | −9.01 pp [−13.06, −4.87] | −6.53 |
| sepsis | −5.65 pp [−10.40, −0.84] | −3.12 ns |
| metabolic | −1.50 ns | +1.33 ns |
| **heterogeneity spread** | **33.55 pp [28.88, 40.89]** | **28.54 [22.99, 35.58]** |

The spread is **larger** in the immune design than in the compromised primary (33.6 vs 23.0 pp), so differential
ascertainment was *diluting* the effect, not creating it.

## 5. Cross-site replication

Two independent hospitals — separate populations, EEG services, readers applying the label, and clinical practice.

| | S0001 (n=1,965) | S0002 (n=1,048) | between-site difference |
|---|---|---|---|
| 30-day spread | 33.77 pp [27.73, 42.12] | 37.95 pp [31.84, 49.60] | −4.18 [−17.36, +5.45] — **agree** |
| 90-day spread | 28.66 pp [23.16, 37.09] | 30.97 pp [23.57, 43.13] | −2.31 [−15.94, +8.39] — **agree** |

Per-aetiology terms are near-identical across sites (anoxic +23.80 vs +25.35; status −9.97 vs −12.60). The
between-site difference is **bootstrapped directly** rather than compared by significance.

## 6. What this cannot claim

1. **Not causal.** Aetiology is not randomised; sicker patients receive more sedation *and* more EEG monitoring.
2. **Indication bias is severe and unfixable.** Continuous EEG is ordered *because* clinicians are worried. This
   is a cohort of patients someone was concerned about, not a sample of ICU patients. Splitting by site does not
   address it — it applies equally at both.
3. **Burst suppression is a clinician label** on a report, not a quantified burden. Reader heterogeneity is an
   unmeasured error source. Running the project's validated raw-EEG detector on the source EDFs is the obvious
   upgrade and is not done.
4. **Cross-site, not cross-system.** Both sites share a health system, region, reporting infrastructure and OMOP
   instance. This rules out single-reader and single-unit artefacts; it does not rule out something institutional.
5. **45.7 % of the burst-suppression cohort has no aetiology label at all** — the group the review calls
   "challenging to determine", and the least-ascertained one. It is excluded from the interaction model rather
   than explained.
6. **Coverage is 95 % of patients but not of their code lists.** Incomplete lists under-call aetiology and
   attenuate toward null. Every figure here should strengthen at full extraction, and all will be re-run.

## 7. Relationship to the VitalDB work

The VitalDB analysis (`37_BROWN_SUMMARY.md`) establishes, at sub-minute resolution in a controlled setting, that
burst suppression is followed by a vasodilatory pressure fall specific to the suppressed state rather than to
anaesthetic depth. It is *motivating physiology* — evidence that the state acts on the body — and it speaks to the
review's third quote about brain–body interaction.

It does not validate this study, and this study does not validate it. Different populations, timescales and
questions. The VitalDB effect is small (0.33 mmHg), has no demonstrated clinical consequence, and its sympathetic
step could not be measured after three instruments failed.
