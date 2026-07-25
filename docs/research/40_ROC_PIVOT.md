# A second study, from a Brown-lab paper's own stated future direction

**Status: feasibility CONFIRMED, extraction running, no results yet.** This document exists so the design is on
record before any outcome is seen.

## 1. The paper, and the sentence that opens the door

Safavynia SA, …, Brown EN. *Determinants of Delayed Recovery of Consciousness After Analgosedation
Discontinuation in the ICU: Insights From Patients With COVID-19 Hypoxemic Respiratory Failure.*
**Crit Care Med 2026**, PMID 42294965, doi:10.1097/CCM.0000000000007205. MGH / Weill Cornell / Columbia,
784 patients.

What they found: **34 % of patients who recovered consciousness did not do so within pharmacologically plausible
sedative elimination times.** Prolonged unconsciousness after ICU sedation is routinely attributed to residual
drug in the setting of reduced clearance. In a third of patients, that explanation does not fit.

Their conclusion, quoted from the abstract:

> "In our cohort, the time to RoC was commonly prolonged beyond that expected from sedation exposures alone."

> findings "warrant **investigation of alternative determinants of delayed RoC** in this population."

That is a stated, unresolved future direction from a paper Brown is an author on. It names the gap and does not
fill it.

## 2. What we can contribute that they could not

**The alternative determinant is plausibly visible on the EEG, and they did not have EEG.**

The hypothesis: *a brain that enters burst suppression under ordinary sedative doses is a brain whose recovery
will outlast the drug.* Suppression at a given exposure is a readout of how the cortex is responding, not of how
much drug is present — so it should predict late recovery **after** conditioning on the drug exposure that the
Safavynia model already accounts for. If it does, the "alternative determinant" they call for is a measurement
already being made at the bedside in most of these patients.

| | Safavynia 2026 | this |
|---|---|---|
| n | 784 | 49,232 EEG patients (cohort to be defined by sedation + assessment availability) |
| population | COVID-19 hypoxaemic respiratory failure, Spring–Summer 2020 | unselected ICU/inpatient, multi-year |
| EEG | none | clinician-reported findings on 129,831 reports, plus raw EDF |
| sedation | time-weighted dose at cessation | OMOP `drug_exposure`, 23.6 M rows, with start/end datetimes |
| consciousness | chart-derived RoC | OMOP `measurement`: GCS total + components, RASS, level-of-consciousness |

Their own limitation — a single disease in a single season, offered explicitly "as a framework for the broader
critically ill population" — is the thing a large unselected cohort is for.

## 3. Why this outcome is methodologically better than the one we have

The burst-suppression mortality study (`39_HEEDB_FINDINGS.md`) is constrained by an outcome defect that cost it
two of its five pre-specified tests: death-record completeness varies by aetiology (40.1–61.9 %), so "died" is
differentially ascertained and the surviving analyses had to be restricted to patients who all died, comparing
only *how soon*. Nothing there estimates the risk of death itself.

**Recovery of consciousness is ascertained in-hospital, from repeated nurse-recorded scores, and does not depend
on death-registry linkage at all.** It is measured on everyone who is assessed, survivors included. That removes
the single largest methodological compromise in the existing work.

## 4. Feasibility check, already done

Two of 551 `measurement` parquet parts, filtered to the 49,232 EEG patients, contain:

| source value | rows in 2/551 parts |
|---|---|
| LEVEL OF CONSCIOUSNESS | 31,010 |
| EYE OPENING | 18,097 |
| BEST MOTOR RESPONSE | 18,073 |
| GLASGOW COMA SCALE SCORE | 18,062 |
| BEST VERBAL RESPONSE | 13,716 |
| R PHS IP RASS | 9,785 |
| PATIENT RASS SCORE | 7,205 |
| *(184 distinct consciousness-related source values in total)* | |

34,231 rows kept from 2 parts → order 9 M rows at full extraction. Running now, ~6 h.
`heedb_omop_extract.py` gained a row-filtered pseudo-table (`measurement_conscious`) for this: the merged
measurement table is 66 GB of every lab and vital sign, and only the consciousness assessments are wanted.

## 5. Design commitments, made before any outcome is seen

1. **The exposure must be conditioned on drug exposure, not compared to it.** The claim is only interesting if
   suppression predicts late recovery *after* the sedative dose is in the model. A univariate association would
   just re-find what they already attribute to drug.
2. **Dexmedetomidine is a pre-specified moderator, not a nuisance.** Safavynia report that patients receiving it
   as an adjunct "had a disproportionately larger incidence of early recovery". Dexmedetomidine does not produce
   burst suppression at clinical doses — it acts through α2 receptors in locus coeruleus and yields a
   spindle-rich, sleep-like EEG. So it is both an independent check on their finding and a mechanistic contrast.
3. **Time zero is sedation discontinuation**, matching their design, so the two are comparable.
4. **Left-censoring and competing risk must be handled explicitly.** Death before recovery is a competing risk,
   not a censoring event; they used a subdistribution hazard model and so should we.
5. **The known trap.** Patients who are deeply suppressed get sedation stopped *earlier* precisely because they
   look over-sedated. That is confounding by indication running in the direction of the hypothesis, and it needs
   a pre-specified handle — most likely restriction to patients whose sedation stopped for a protocolised reason
   — before any estimate is believed.

## 6. Relationship to the existing work

This does not replace `39_HEEDB_FINDINGS.md`; it is a second, independent question from the same cohort and the
same literature. The burst-suppression phenotype work answers the review's "characterize distinct burst
suppression phenotypes" call. This answers a different paper's "alternative determinants of delayed RoC" call.
They share the exposure and share none of the outcome machinery, so a failure of one does not implicate the other.

## 7. Honest statement of what is not yet known

No model has been fit. It is not established that HEEDB patients have consciousness assessments densely enough
around sedation cessation to define time-to-recovery, nor that enough of them have both an EEG and a sedation
episode. Those are the next two checks and either could end this. Recorded here so that if it dies, it is on
record as having died rather than quietly disappearing.
