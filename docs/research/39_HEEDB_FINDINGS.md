# Burst suppression is not one entity: its prognostic meaning depends on aetiology

**HEEDB, 49,231 patients with inpatient/ICU EEG linked to the OMOP clinical record. 7,323 with burst suppression
labelled across 22,057 reports. Two independent hospital sites.**

*Analysis plan pre-registered in `38_HEEDB_BS_PHENOTYPE_SAP.md` and committed before the cohort was assembled.
All figures below are at **full extraction** (22,263,086 condition rows; 99.9 % of the target patient set),
superseding the partial-coverage numbers reported earlier. Every effect **strengthened** at full coverage, which
was the direction predicted in advance and is what incomplete aetiology coding should do (under-called aetiology
attenuates toward null). §8 records the prediction against the outcome.*

---

## 0. Reconciling the cohort counts, because they differ by design

Several different denominators appear below and they are easy to mistake for inconsistencies. All are verified
directly against the extracted files.

| count | what it is |
|---|---|
| 49,231 | EEG patients with a timestamped report |
| 7,323 | of those, with burst suppression labelled on at least one report |
| **16,244** | the **extraction cohort**: EEG patients with a death record in the OMOP `death` table. Deliberately death-restricted — every surviving test is ascertainment-immune and needs no survivors |
| 16,233 | of those, who also have ≥1 condition row (22,263,086 rows total; 99.9 % of the target list) |
| **15,318** | analysable for the specificity test: condition data **and** an EEG time **and** an ascertained death (3,106 BS-positive / 12,212 BS-negative) |
| 3,302 | burst-suppression patients present in the death-restricted condition file. Only 3,304 of the 7,323 BS patients have a death record at all, so this is the expected ceiling, **not** a sign of incomplete extraction |
| 3,216 | of those, who also have an EEG time — the ascertainment-immune analysis cohort of §4 and §5 |

One caveat for anyone re-running the code: `heedb_bs_phenotypes.py` prints a "condition extraction only 45 %
complete" warning, triggered by a heuristic that compares condition coverage against the *whole* 7,323-patient BS
cohort. Against a death-restricted extraction that heuristic is wrong by construction — the reachable maximum is
3,304, not 7,323 — and the warning should be ignored for these runs. It is left in place because it is correct
for the unrestricted extraction it was written for.

The two condition extractions differ in **depth**, not just in cohort, and this matters for §6a: the unrestricted
BS-only file holds a median of 168 condition codes per patient, the deep extraction 730. Both figures are
computed directly from the CSVs (`person_id` value counts), not taken from a log.

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
| aetiology effect in **BS-negative** patients — the honest denominator | 12.13 pp [8.44, 15.84] |
| **BS × aetiology interaction** | 38.51 pp [32.84, 44.63] |
| **difference (interaction − main effect), paired bootstrap** | **+26.38 pp [+20.27, +32.68]** |

The bottom row is the statistic the claim rests on. Reporting the first two rows and observing that one is
larger would be the comparison-of-significance shortcut this project has committed four times: non-overlapping
intervals are evidence, but they are not a test of the difference. Both spreads are computed from the same
resample index on every replicate, so they are differenced per replicate. The difference excludes zero, so the
heterogeneity is **specific to burst suppression** rather than inherited from the diagnosis.

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
| **specificity** — is it burst suppression or just aetiology? | ✓ difference +26.38 pp [+20.27, +32.68] — see §2 |
| *(added)* **dose-response on measured burden**, replacing the label | ✓ interaction 32.63 pp [25.03, 40.89]; monotone gradient to 86.6 % — see §6b |

Three of five pre-specified tests pass, plus the added dose-response test in §6b. Two are demoted for a defect the red-team found in the outcome variable
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

The immune design gives a larger spread than the compromised primary (36.8 vs 23.0 pp). **That comparison should
not be read as telling us which way the bias ran**, and an earlier version of this document wrongly did so. The
two analyses estimate different quantities on different cohorts — "was a death ever recorded", across all
burst-suppression patients, versus "did death come within 30 days", among decedents only — so their magnitudes
are not commensurable and their difference carries no information about the direction of ascertainment bias. The
justification for demoting the primary is that its outcome is invalid *in principle* when recording completeness
varies by exposure group, which is established by the table above and requires no appeal to the observed
direction.

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
3. ~~Burst suppression is a clinician label~~ — **resolved, see §6b.** Measured burden reproduces the
   interaction and yields a monotone dose-response, so reader heterogeneity cannot explain the finding.
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
- ~~H2 re-test~~ — **run, and it failed. H2 remains unresolved; see §7a.**
- ~~Characterising the unexplained group~~ — **done, see §6a.** It is 6.6 % of the cohort, 91 % of it epilepsy
  without status epilepticus, and prognostically neutral.

## 6b. The finding survives without the clinician label, and is graded

The central result rested on a binary label written by whichever neurophysiologist read the study — so a reader
systematically liberal in post-arrest patients would produce exactly this aetiology-dependent pattern. That was a
live alternative explanation, not a hypothetical.

Burst-suppression **burden** was therefore measured directly from the raw EDF on 28,657 recordings by a detector
calibrated in-distribution against HEEDB's own expert labels. It reproduces out-of-sample here at **AUC 0.783
[0.769, 0.800]** (median burden 0.471 in clinician-positive patients against 0.016 in negatives). Both
predictions below were registered and committed before the burden data existed.

**D1 — the interaction reproduces without the label (n = 7,477; 32.7 % labelled, 67.3 % not).**

| aetiology | burden × aetiology interaction |
|---|---|
| **anoxic** | **+13.15 pp** |
| status epilepticus | +1.00 pp |
| sepsis | −8.13 pp |
| metabolic | −12.26 pp |
| structural | −19.49 pp |
| **spread** | **32.63 pp [25.03, 40.89]** |

Anoxic is the largest positive term and the spread excludes zero, as predicted. The *ordering* of the middle
terms differs from the label-based version (there: anoxic, metabolic, status, structural, sepsis) — the
prediction was registered on anoxic's rank and the spread, not on the full ordering, and the middle terms should
not be over-read.

**D2 — a monotone dose-response, which the binary label could not test.** Within anoxic patients (n = 1,875),
30-day death rises with measured burden at **+50.81 pp per unit burden [+45.94, +55.62]**:

| burden quartile | 30-day death |
|---|---|
| Q1 lowest | 35.6 % |
| Q2 | 47.6 % |
| Q3 | 66.2 % |
| Q4 highest | **86.6 %** |

**This removes limitation #3 and adds the strongest form of observational evidence available.** Reader
heterogeneity cannot explain a gradient in a quantity no reader produced.

*A correction on the way here.* A first run of this test reported D1 as falsified. It was wrong: it imported an
EEG-time helper that returns times only for BS-labelled patients, so the model fit inside the BS-positive group
with the comparison group absent. The tell was the exposure distribution — median burden 0.439 in the analysable
set against 0.053 in the population — not any coefficient. Fixed, and the script now refuses to report the
interaction as comparable if the analysable set is more than 90 % labelled.

## 7a. The H2 re-test failed, and the negative control is why we know

H2 — "iatrogenic suppression carries a better outcome than injury suppression" — was demoted in §3 for using the
differentially-ascertained outcome. It was re-tested properly: ascertainment-immune outcome, and an exposure
anchored to within 24 h of the EEG and restricted to agents that can actually produce the state (propofol, the
barbiturates, high-dose midazolam). The unexposed group is then the interesting one — a cortex that suppressed
with no pharmacological explanation. **Prediction, registered before the fit: a negative coefficient.**

| | 30-day coefficient | predicted |
|---|---|---|
| BS-capable anaesthetic within ±24 h (61.7 %) | **+31.00 pp [+27.50, +34.67]** | negative — **falsified** |
| dexmedetomidine, negative control (17.4 %) | **−8.13 pp [−12.70, −3.55]** | null — **also violated** |

Both predictions failed, and together they diagnose the design. Dexmedetomidine sedates but does not produce
burst suppression, so it was included to separate "given a drug that suppresses" from "sedated at all". It came
out significantly *protective*. The coherent reading is that neither variable is measuring pharmacology: peri-EEG
propofol marks an intubated, actively-resuscitated patient, and dexmedetomidine marks one stable enough to be
lightly sedated and weaned. Both are **illness-severity proxies**. A corroborating detail: the anoxic coefficient
falls from +29.45 to +20.46 pp when the drug term enters, i.e. the drug variable absorbs severity that aetiology
had been carrying.

**So H2 is unresolved, not answered.** Separating iatrogenic from injury suppression needs an exposure that is
not a severity proxy, and administrative drug records in an ICU cohort are severity proxies by default.

This is reported because it is the kind of result that does not survive contact with a reviewer: +31 pp is large,
clean and significant, and without the pre-specified negative control it would have been written up as a finding
in the wrong direction with a story attached.

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

Predictions made about *new* quantities, where the evidence is not weak, have fared worse:

| prediction | registered | outcome | verdict |
|---|---|---|---|
| epilepsy-without-status is negative (§6a) | −ve | +2.13 pp [−3.81, +8.09] | **failed** |
| BS-capable anaesthetic is negative (§7a) | −ve | +31.00 pp [+27.50, +34.67] | **failed, opposite sign** |
| dexmedetomidine negative control is null (§7a) | null | −8.13 pp [−12.70, −3.55] | **failed** |

Three of the first three registered predictions about new quantities failed; the two most recent (D1 and D2 in
§6b, the ones the central claim actually depends on) were **confirmed**. Both failures share one root cause worth
stating plainly: I twice reasoned "this suppression is pharmacological, therefore the patient is doing better",
when a pharmacological cause actually predicts that the EEG carries *no* information (a null), and when the drug
record itself turned out to be measuring severity rather than pharmacology. The confirmatory result in §2–§5 does
not rest on any of these.

## 9. Relationship to the VitalDB work

The VitalDB analysis (`37_BROWN_SUMMARY.md`) establishes, at sub-minute resolution in a controlled setting, that
burst suppression is followed by a vasodilatory pressure fall specific to the suppressed state rather than to
anaesthetic depth. It is *motivating physiology* — evidence that the state acts on the body — and it speaks to
the review's third quote about brain–body interaction.

It does not validate this study, and this study does not validate it. Different populations, timescales and
questions. The VitalDB effect is small (0.33 mmHg), has no demonstrated clinical consequence, and its sympathetic
step could not be measured after three instruments failed.
