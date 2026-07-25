# Burst suppression is not one entity: its prognostic meaning depends on aetiology

**HEEDB, 49,231 patients with inpatient/ICU EEG linked to the OMOP clinical record. 7,323 with burst suppression
labelled across 22,057 reports. Two independent hospital sites.**

*Analysis plan pre-registered in `38_HEEDB_BS_PHENOTYPE_SAP.md` and committed before the cohort was assembled.
All figures below are at **full extraction** (22,263,086 condition rows; 99.9 % of the target patient set),
superseding the partial-coverage numbers reported earlier. Every effect **strengthened** at full coverage, which
was the direction predicted in advance and is what incomplete aetiology coding should do (under-called aetiology
attenuates toward null). §8 records the prediction against the outcome.*

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

Among 15,318 patients with an ascertained death (3,106 with burst suppression, 12,212 without), death within
30 days of the EEG:

| | spread across aetiologies |
|---|---|
| aetiology effect in **BS-negative** patients — the honest denominator | **12.13 pp** [8.44, 15.84] |
| **BS × aetiology interaction** | **38.51 pp** [32.84, 44.63] |

The interaction is **3.2× the aetiology main effect**, so this is specific to burst suppression, not inherited
from the diagnosis.

| aetiology | interaction term | reading |
|---|---|---|
| **anoxic** | **+23.59 pp** | suppression is a grave sign |
| metabolic | −1.41 pp | |
| status epilepticus | −5.84 pp | |
| structural | −9.28 pp | |
| **sepsis** | **−14.92 pp** | suppression carries little weight |

In post-anoxic injury, burst suppression marks a brain that is dying. In sepsis it is close to uninformative —
plausibly because there it reflects sedation rather than injury.

### This supplies a mechanism for the heterogeneity the review describes
A cohort dominated by post-arrest patients will find burst suppression ominous. A cohort dominated by septic
patients will find it benign. **Both are correct about their own case mix.** Pooling them — which the outcome
literature does — produces exactly the contradictory findings Guay and Brown point to. The heterogeneity is not
noise; it is aetiological composition.

## 3. The five pre-specified tests

| test | result |
|---|---|
| **primary** — mortality heterogeneity across aetiologies | **DEMOTED — see §4.** Compromised by differential ascertainment, and not re-runnable at full coverage |
| **secondary H2, direction fixed in advance** — iatrogenic < injury | **DEMOTED** — same outcome variable, same defect. Re-test pending, see §7 |
| **ascertainment red-team** | ✓ survives, and **larger** — 36.80 pp, see §4 |
| **cross-site replication**, formal agreement statistic | ✓ both sites agree — see §5 |
| **specificity** — is it burst suppression or just aetiology? | ✓ 38.51 vs 12.13 pp — see §2 |

Three of five pre-specified tests pass. Two are demoted for a defect the red-team found in the outcome variable
itself, and the finding now rests entirely on the ascertainment-immune design. That demotion is reported here
rather than buried because the demoted analysis is the one the plan called "primary".

## 4. The ascertainment red-team, which the primary analysis failed

Death-record completeness varies sharply across the five modelled aetiologies — from **40.1 %** to **61.9 %**, a
**21.8 pp** differential:

| | anoxic | sepsis | metabolic | structural | status |
|---|---|---|---|---|---|
| n | 1,457 | 1,074 | 2,493 | 1,932 | 773 |
| death record present | **61.9 %** | 57.4 % | 56.6 % | 51.8 % | **40.1 %** |

Coding "no death record" as *survived* therefore **manufactures** a spread, and in precisely the observed
direction. The pre-specified primary and H2 both used that outcome. **Both are compromised and are demoted.**

The replacement holds ascertainment constant by construction: restrict to patients who **all** have a recorded
death, and ask how *soon* after the EEG they died. What is compared is how quickly patients died, not whether a
death was captured — so differential recording cannot contribute.

*(n = 3,216 patients with a death record and an EEG time; median 16 days from EEG to death.)*

| | 30-day (baseline 56.8 %) | 90-day (baseline 64.5 %) |
|---|---|---|
| anoxic | +29.52 pp [+25.99, +32.83] | +25.24 pp [+22.08, +28.46] |
| metabolic | +5.44 pp [+1.93, +8.95] | +6.20 pp [+2.56, +9.88] |
| sepsis | −2.46 pp [−5.77, +0.94] ns | +2.15 pp ns |
| structural | −2.49 pp [−6.00, +0.71] ns | −1.51 pp ns |
| status epilepticus | −7.29 pp [−11.42, −2.94] | −5.50 pp [−10.07, −0.97] |
| **heterogeneity spread** | **36.80 pp [32.09, 41.93]** | **30.74 pp [26.17, 35.85]** |

The spread is **larger** in the immune design than in the compromised primary (36.8 vs 23.0 pp), so differential
ascertainment was *diluting* the effect, not creating it.

**Note on provenance.** The ascertainment rates above must be measured on a universe that is *not* itself
restricted to patients with a death record. The main 16,244-patient extraction **is** so restricted — the cohort
was defined as "EEG patient with an ascertained death", because every surviving test is ascertainment-immune and
needs no survivors. Measuring an ascertainment rate inside that file returns 100 % in every stratum by
construction; it is the cohort definition read back, not a result. The rates above therefore come from the only
unrestricted extraction available (7,102 BS patients, 44.5 % with a death record). That file is **shallower** —
median 168 condition codes per patient against 730 in the deep extraction — so its aetiology labels are
under-called and the measured differential is attenuated toward the cohort mean. The 21.8 pp spread is therefore
a *lower bound* on the true differential, which is the conservative direction for the argument it is being used
to make. For the same reason the unexplained stratum is not reported here: in a shallow extraction "no aetiology
code" mostly means "not yet extracted", and its apparent ascertainment rate is not interpretable.
`heedb_bs_ascertainment.py` now refuses to report CHECK 1 if the universe it is handed is death-restricted, and
`heedb_bs_phenotypes.py` aborts
rather than fit a model whose outcome has no variance — that degenerate fit prints as `0.00 pp ns`, which is
indistinguishable from a genuine null and was briefly mistaken for one.

## 5. Cross-site replication

Two independent hospitals — separate populations, EEG services, readers applying the label, and clinical practice.

| | S0001 (n=2,096) | S0002 (n=1,120) | between-site difference |
|---|---|---|---|
| 30-day spread | 35.91 pp [30.01, 42.55] | 38.08 pp [33.68, 47.14] | −2.17 [−13.36, +5.38] — **agree** |
| 90-day spread | 31.10 pp [25.31, 37.52] | 29.86 pp [24.64, 38.53] | +1.24 [−9.65, +8.87] — **agree** |

Per-aetiology terms are near-identical across sites (anoxic +28.58 vs +31.12; status −7.33 vs −6.96; metabolic
+5.04 vs +6.50). The between-site difference is **bootstrapped directly** rather than inferred from whether each
site's interval separately excludes zero — that comparison-of-significance shortcut is an error this project has
made four times and now tests against explicitly.

## 6. What this cannot claim

1. **Not causal.** Aetiology is not randomised; sicker patients receive more sedation *and* more EEG monitoring.
2. **Indication bias is severe and unfixable.** Continuous EEG is ordered *because* clinicians are worried. This
   is a cohort of patients someone was concerned about, not a sample of ICU patients. Splitting by site does not
   address it — it applies equally at both.
3. **Burst suppression is a clinician label** on a report, not a quantified burden. Reader heterogeneity is an
   unmeasured error source. Being fixed — see §7.
4. **Cross-site, not cross-system.** Both sites share a health system, region, reporting infrastructure and OMOP
   instance. This rules out single-reader and single-unit artefacts; it does not rule out something institutional.
5. **The surviving analyses are conditioned on having died.** They compare *how soon* among decedents. This is
   what buys immunity to differential ascertainment, and the price is that nothing here estimates the risk of
   death itself. The demoted primary was the analysis that would have, and it is not trustworthy.
6. **The residual unexplained group is small but is excluded rather than modelled** — 6.6 % of the analysed
   cohort, and only 0.6 % after the refinement in §6a. Small enough not to threaten the result; still excluded.
7. **No external replication.** VitalDB is the only public source with simultaneous high-resolution EEG and
   continuous arterial pressure, and it holds no ICU outcome data; MIMIC-IV/III Waveform, I-CARE, BDSP-SAH and
   the PSG collections were each checked and none carries the required combination. This finding is
   cross-site-replicated but not externally replicated, and no accessible dataset can currently change that.

## 6a. What the "challenging to determine" group actually is *(exploratory)*

The review's first quote says determining the exact aetiology "can be challenging". In the analysed cohort that
difficulty is smaller than it first appeared, and it is not miscellaneous.

**6.6 %** of burst-suppression patients (219 / 3,302) carry none of the five pre-registered aetiologies. Their
codes are dominated by seizure disorder that does not meet the status-epilepticus definition — other/unspecified
convulsions (42 %, 38 %) and epilepsy without status (26 %, 23 %, plus eight further variants). This is not a
coding gap: `G40909` differs from `G40901` in exactly the digit encoding *without status epilepticus*, and the
pre-registered dictionary matches only the with-status codes, which is what it was written to do.

Adding a sixth `epilepsy-without-status` category absorbs **90.9 %** of the unexplained group, leaving **0.6 %**
of the cohort (20 patients) genuinely unclassified.

**A registered prediction that failed.** Before fitting, the prediction on record was that this group's 30-day
coefficient would be **negative** — the reasoning being that in epilepsy without status, suppression is
pharmacological (anti-seizure and anaesthetic infusions in a brain that is not structurally dying) and should
therefore resemble status epilepticus (−7.48 pp) rather than anoxic injury (+29.45 pp). It came out
**+2.13 pp [−3.81, +8.09], null** — positive-signed and indistinguishable from zero, which meets the
pre-stated falsification criterion. The group is prognostically **neutral**: it carries neither the grave meaning
suppression has after anoxia nor the protective-looking signal seen in status. The "pharmacological therefore
benign" reading is not supported; "pharmacological therefore uninformative" is what the data show.

*Exploratory throughout: the sixth category was defined after inspecting the codes, so it does not enter the
confirmatory result. The prediction was committed to the repository before the model was fit.*

**A correction this supersedes.** Earlier versions of this document reported that 45.7 % of the cohort had no
aetiology label, and listed it as the study's largest limitation. That figure — and a 35.4 % revision of it —
came from a shallower extraction (median 168 condition codes per patient against 730 in the deep one), where
"no aetiology code" mostly meant "not yet extracted". At full per-patient depth the true figure is 6.6 %. The
limitation was substantially an artefact of incomplete extraction, not a property of the cohort.

## 7. In flight

- **Quantified burden** replacing the binary label (`heedb_bs_quantify.py`), using the detector calibrated
  against HEEDB's own expert labels at AUC 0.829. Enables a dose-response — the strongest observational evidence
  available for a real effect — and removes reader heterogeneity. Running over 51,702 recordings.
- **H2 re-test** inside the ascertainment-immune design: drug-derived sedative exposure against the 30-day timing
  outcome, replacing the demoted version. Gated on the `drug_exposure` extraction, which is ~60 % complete.
- ~~Characterising the unexplained group~~ — **done, see §6a.** It is 6.6 % of the cohort, 91 % of it epilepsy
  without status epilepticus, and prognostically neutral.

## 8. Prediction ledger entry

Before the full-coverage runs, the prediction on record was that every effect should **strengthen**, because
incomplete per-patient code lists under-call aetiology and attenuate toward null; and that weakening or reversal
would indicate the partial-coverage results were selection-driven and would be reported instead of the earlier
numbers. Outcome:

| figure | partial coverage | full coverage | direction |
|---|---|---|---|
| specificity interaction spread | 36.17 pp | **38.51 pp** | strengthened ✓ |
| ascertainment-immune 30-day spread | 33.55 pp | **36.80 pp** | strengthened ✓ |
| S0001 30-day spread | 33.77 pp | **35.91 pp** | strengthened ✓ |
| S0002 30-day spread | 37.95 pp | **38.08 pp** | strengthened ✓ |

Four of four in the predicted direction. This is weak evidence — the two runs share most of their data, so the
comparisons are not independent — but it is the prediction that was made, and it is recorded as made.

## 9. Relationship to the VitalDB work

The VitalDB analysis (`37_BROWN_SUMMARY.md`) establishes, at sub-minute resolution in a controlled setting, that
burst suppression is followed by a vasodilatory pressure fall specific to the suppressed state rather than to
anaesthetic depth. It is *motivating physiology* — evidence that the state acts on the body — and it speaks to
the review's third quote about brain–body interaction.

It does not validate this study, and this study does not validate it. Different populations, timescales and
questions. The VitalDB effect is small (0.33 mmHg), has no demonstrated clinical consequence, and its sympathetic
step could not be measured after three instruments failed.
