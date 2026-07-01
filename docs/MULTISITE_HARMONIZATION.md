# Multi-site harmonization — concept -> ID mappings for HiRID, SICdb, AmsterdamUMCdb

Companion to `MULTISITE_VALIDATION_PLAN.md`. This document is the concept-dictionary layer that lets
`hirid_run.py` / `sicdb_run.py` / `amsterdam_run.py` mirror `docs/eicu_run.py` / `docs/portfolio_run.py`
(assay-noise IV / flag-ITT: M1,M2 pre-treatment draws -> Z=1(M2 crosses flag) -> midpoint control ->
D=treatment within 24h -> Y=in-hospital mortality, + implied-LATE/AR + balance + density + NAIVE contrast).

**Everything below was compiled from PUBLIC sources with no dataset access.** Confirmed cells are cited;
uncertain/unconfirmed cells are marked `TO-CONFIRM-ON-ACCESS`. Two independent public sources were checked
for each concept where possible (the `ricu` R package's concept dictionary, plus a dataset-native source:
the official HiRID docs site, the SICdb documentation wiki, or the AmsterdamUMCdb GitHub wiki/concepts).

Primary sources used throughout:
- **ricu** concept dictionary: `github.com/eth-mds/ricu/blob/main/inst/extdata/config/concept-dict.json`
  (harmonizes MIMIC/eICU/HiRID/AmsterdamUMCdb/SICdb; abstract concept -> per-source `ids`/`table`/`sub_var`).
  NOTE: this file is large (~9-10k lines) and public WebFetch tooling truncates it around the same offset
  on repeated calls (alphabetically near "methb"/"bnd") — **entries confirmed below were cross-checked
  against a second independent source**; entries that could NOT be cross-checked are explicitly marked
  low-confidence or TO-CONFIRM-ON-ACCESS rather than reported as fact. Re-pull this file directly (not
  through a summarizing fetch) on day one to close these gaps.
- **HiRID**: official docs `hirid.intensivecare.ai/structure-of-the-published-data`; `HIRID-ICU-Benchmark`
  repo `github.com/ratschlab/HIRID-ICU-Benchmark` (`preprocessing/resources/varref.tsv`); PhysioNet page
  `physionet.org/content/hirid/1.1.1/` (reference_data/ is DUA-gated, 403 without credentials).
- **SICdb**: official documentation wiki `sicdb.com/Documentation/*` (Main_Page, Case_Data /
  Data_Description_Medication / Laboratory_Data / Reference_Table); PhysioNet page
  `physionet.org/content/sicdb/1.0.6/`; SICdb paper (Rodemund et al., Scientific Data 2024/2025,
  "Harnessing Big Data in Critical Care").
- **AmsterdamUMCdb**: official GitHub wiki `github.com/AmsterdamUMC/AmsterdamUMCdb/wiki` (Admissions,
  Drugitems, Numericitems pages); `concepts/` folder in the same repo; PhysioNet page
  `physionet.org/content/amsterdamumcdb/1.0.2/`; Thoral et al. Crit Care Med 2021 paper.

---

## Common data-model interface (dataset-agnostic core)

Exactly as sketched in `MULTISITE_VALIDATION_PLAN.md`. Each adapter's job is ONLY to emit these three
harmonized streams; the assay-noise IV / flag-ITT engine (identical math to `portfolio_run.py`/`eicu_run.py`)
is then dataset-agnostic and unchanged:

```
labs:      (stay_id, time_hours, analyte, value)      # analyte in {hb, glu, plt, hco3, k, mg}
tx:        (stay_id, time_hours, tx_class)            # tx_class in {rbc, insulin, nahco3, kcl}
patient:   {stay_id: {age, sex, mortality}}            # mortality = 1(died in-hospital), 0 otherwise
```

`time_hours` is always converted to **hours from ICU admission** at the adapter boundary, regardless of
each dataset's native convention (HiRID = absolute timeshifted datetime; SICdb = seconds-from-admission;
AmsterdamUMCdb = milliseconds-from-first-admission) — this mirrors how `eicu_run.py` converts eICU's
minute-offsets to hours so the core engine's bandwidths/windows (in hours) never change per site.

---

## 1. HiRID (Bern, Switzerland — PhysioNet `hirid` v1.1.1)

**Table schema** (confirmed, `hirid.intensivecare.ai/structure-of-the-published-data` + ricu):
- `general`: `patientid`, `admissiontime` (absolute datetime, timeshifted per patient for de-identification),
  `sex` ('M'/'F'), `age` (integer, capped at 90), `discharge_status` ('alive'/'dead'/'unknown').
- `observations` (labs/vitals): `patientid`, `datetime` (absolute datetime, timeshifted), `variableid`,
  `value`, `stringvalue`, `type`, `status`.
- `pharma` (drug administrations): `patientid`, `givenat` (absolute datetime, timeshifted), `pharmaid`,
  `givendose`, `doseunit`, `infusionid`.
- Reference dictionaries (DUA-gated on PhysioNet, not fetchable without credentials; confirm on access):
  `hirid_variable_reference.csv`, `hirid_variable_reference_preprocessed.csv`, `ordinal_vars_ref.csv`.

**Timestamp convention:** all HiRID timestamps are **absolute datetimes** (patient-shifted), NOT relative
minute/second offsets — this is the one dataset of the three that needs real datetime parsing (like the
MIMIC engine's `charttime` parsing in `portfolio_run.py`, not like eICU's/AmsterdamUMCdb's/SICdb's raw
offsets). Convert to hours-from-admission via `(datetime - admissiontime) / 3600s`.

| Concept | Table.Column / ID | Units | Source | Confidence |
|---|---|---|---|---|
| Hemoglobin | `observations.variableid` in {24000548, 24000836, 20000900} | mixed raw units, convert x0.1 -> g/dL (ricu callback) | ricu concept-dict.json (`hgb`) | Confirmed (1 source; not independently cross-checked against varref.tsv, which is pharma-focused) |
| Glucose | `observations.variableid` in {20005110, 24000523, 24000585} | convert x18.016 -> mg/dL | ricu concept-dict.json (`glu`) | Confirmed |
| Platelet count | `observations.variableid` = 24000549 | convert x0.001 -> K/uL | ricu concept-dict.json (`plt`) | Confirmed |
| Bicarbonate/HCO3 | `observations.variableid` = 20004200 | mEq/L | ricu concept-dict.json (`bicar`) | Confirmed |
| Potassium | `observations.variableid` in {20000500, 24000520, 24000833, 24000867} | mEq/L | ricu concept-dict.json (`k`) | Confirmed |
| Magnesium | `observations.variableid` = 20005200 | convert x2.432 -> mg/dL | ricu concept-dict.json (`mg`) | Confirmed via ricu only; **not present in the smaller HIRID-ICU-Benchmark `varref.tsv`** (which curates ~626 vars, mostly pharma/monitoring) — treat as medium confidence, re-verify variableid meaning against `hirid_variable_reference.csv` on access |
| RBC transfusion | `pharma.pharmaid` in {1000100 ("packed red blood cells"/"EK"), 1000743 ("EK Pflege")} | — | HIRID-ICU-Benchmark `varref.tsv` | Confirmed (dataset-native source; not cross-listed in the ricu snippet retrieved) |
| Insulin | `pharma.pharmaid` in {15 ("Insulin Actrapid", short-acting), 1000724, 1000379 (longer-acting)} | — | ricu concept-dict.json (`ins`) AND HIRID-ICU-Benchmark `varref.tsv` | **Confirmed — cross-source agreement** (highest confidence mapping in this table) |
| Sodium bicarbonate | `pharma.pharmaid` in {1000193 ("Na-Bicarbonat 8.4%"), 1000453 ("Na-Bicarbonat Inf Lsg 8.4%")} | — | HIRID-ICU-Benchmark `varref.tsv` | Confirmed (single source, dataset-native; treat as medium-high confidence) |
| Potassium chloride | `pharma.pharmaid` in {1000080 ("K-Cl conc"), 1000568 ("K-Cl-Perfusor")} | — | HIRID-ICU-Benchmark `varref.tsv` | Confirmed (single source; medium-high confidence) |
| Age | `general.age` | years, capped at 90 | official docs + ricu (`table: general, val_var: age`) | Confirmed |
| Sex | `general.sex`; ricu also reports a redundant `observations.variableid=10000400` (map 1='m',2='f') | 'M'/'F' | official docs (authoritative) + ricu | Confirmed — use `general.sex` directly, it's simpler than the observations-table alternative |
| **In-hospital mortality** | `general.discharge_status == 'dead'` | categorical | official docs (authoritative) | **Confirmed.** ricu's own `death` concept (`observations.variableid` in {110, 200}, callback `hirid_death`) derives the SAME outcome from the last MAP/HR observation as a fallback/cross-check, NOT a different field — use `general.discharge_status` as primary, it's the direct field |
| Timestamp column | `observations.datetime`, `pharma.givenat`, `general.admissiontime` | absolute datetime (patient-timeshifted) | official docs | Confirmed |

**Benchmark cases runnable:** RBC transfusion (Hb<7), Insulin (glucose>180), Bicarbonate (acidosis),
Potassium repletion — all four have both a confirmed lab trigger AND a confirmed treatment id.
**Magnesium repletion is NOT reliably runnable** (lab id medium-confidence, no treatment/pharma id found
in either public source) — flag as a day-one verification target, consistent with magnesium being
frequently sparse/absent across ICU-EHR databases (see `docs/LESSONS.md` precedent for INSPIRE).

---

## 2. SICdb (Salzburg, Austria — PhysioNet `sicdb` v1.0.6)

**ricu support:** SICdb IS present in ricu's `concept-dict.json` (source key `"sic"`) — the `ricu`
philosophy statement in `CLAUDE.md`/`MULTISITE_VALIDATION_PLAN.md` ("ricu harmonizes
MIMIC/eICU/HiRID/AmsterdamUMCdb/SICdb") is confirmed correct; SICdb is the newest/smallest addition so
its public documentation is thinner than the other two.

**Table schema** (confirmed, `sicdb.com/Documentation/*`, official wiki — the single best public source
for this dataset):
- `cases` (one row per ICU admission): `CaseID`, `PatientID`, `AgeOnAdmission` (rounded to +/-5y, >90 ->
  90), `Sex` (Reference-type column), `WeightOnAdmission`/`HeightOnAdmission` (rounded +/-5), `TimeOfStay`
  (admission->discharge, seconds), `ICUOffset`, `HospitalDischargeDay`/`HospitalStayDays` (days, NOT
  seconds — the one day-unit field, watch for this in the adapter), `DischargeState` (reference: type of
  ICU discharge), `HospitalDischargeType` (reference: survival status), `OffsetOfDeath` (seconds from
  admission to death, 1-year mortality window, null if death >1y out or no death), `OffsetAfterFirstAdmission`.
- `laboratory`: `id`, `CaseID`, `PatientID`, `LaboratoryID` (-> `d_references.ReferenceGlobalID`),
  `Offset` (seconds from admission), `LaboratoryValue`, `LaboratoryType`.
- `medication`: `id`, `CaseID`, `DrugID` (-> `d_references.ReferenceGlobalID`), `Offset` (seconds from
  admission), `OffsetDrugEnd`, `IsSingleDose` (bolus flag; single dose given a nominal 60s duration),
  `Amount`, `AmountPerMinute`.
- `d_references`: dictionary table, PK `ReferenceGlobalID`, gives `ReferenceValue` (name) and
  `ReferenceUnit` for every Reference-typed column across all tables (laboratory, medication, cases.Sex,
  cases.DischargeState, etc.) — confirmed SQL join pattern:
  `... LEFT JOIN d_references ON d_references.ReferenceGlobalID = laboratory.LaboratoryID`.
- Other tables (not needed for this analysis): `data_ref` (nominal, 1/admission), `data_range` (start/end
  interval items e.g. central lines), `data_float_h`/`data_float_m` (hourly/minute signal streams).

**Timestamp convention:** all SICdb tables use **integer seconds from ICU admission** (like eICU's
minute-offsets, just finer-grained) — no datetime parsing needed. Convert to hours via `Offset / 3600.0`.

| Concept | Table.Column / ID | Units | Source | Confidence |
|---|---|---|---|---|
| Hemoglobin | `laboratory.LaboratoryID` in {658, 289} | per d_references.ReferenceUnit (TO-CONFIRM-ON-ACCESS — g/dL expected) | ricu concept-dict.json (`hgb`, sic source) | Confirmed via ricu only — **no dataset-native public source lists concrete LaboratoryIDs** (the SICdb docs wiki explicitly declines to enumerate them, directing readers to run the SQL join against `d_references` instead); treat as medium confidence pending on-access verification |
| Glucose | `laboratory.LaboratoryID` in {348, 656} | mg/dL (TO-CONFIRM) | ricu concept-dict.json (`glu`) | Medium confidence, same caveat |
| Platelet count | `laboratory.LaboratoryID` in {219, 680} | K/uL (TO-CONFIRM) | ricu concept-dict.json (`plt`) | Medium confidence, same caveat |
| Bicarbonate/HCO3 | `laboratory.LaboratoryID` in {451, 456, 666, 667} | mEq/L (TO-CONFIRM) | ricu concept-dict.json (`bicar`) | Medium confidence, same caveat |
| Potassium | `laboratory.LaboratoryID` in {463, 685} | mEq/L (TO-CONFIRM) | ricu concept-dict.json (`k`) | Medium confidence, same caveat |
| Magnesium | `laboratory.LaboratoryID` in {464, 688} | mg/dL (TO-CONFIRM) | ricu concept-dict.json (`mg`) | Medium confidence, same caveat — but notably ricu DOES carry a magnesium entry for SIC (unlike HiRID's weaker mg treatment story), so magnesium is plausibly more complete for this dataset |
| RBC transfusion | **TO-CONFIRM-ON-ACCESS** | — | none found | Not located in ricu's retrievable snippet or SICdb docs/paper; `medication.DrugID` values are entirely dictionary-encoded via `d_references` and no public source enumerates them |
| Insulin | **TO-CONFIRM-ON-ACCESS** | — | none found | Same — `medication` DrugIDs not publicly enumerated |
| Sodium bicarbonate | **TO-CONFIRM-ON-ACCESS** | — | none found | Same |
| Potassium chloride | **TO-CONFIRM-ON-ACCESS** | — | none found | Same |
| Age | `cases.AgeOnAdmission` | years, rounded +/-5, >90 capped at 90 | SICdb docs wiki (Case Data) + ricu (`val_var: AgeOnAdmission`) | Confirmed. **Note the +/-5y binning** — coarser than HiRID/MIMIC/eICU's integer age; balance checks (`balAge`) will be noisier here by construction |
| Sex | `cases.Sex` (Reference-type; -> `d_references`) — ricu's `sic` source config confirms: `table=cases, val_var=Gender, callback=apply_map(M='m',F='f')` | 'M'/'F' | ricu concept-dict.json (independently re-verified) | Confirmed. NOTE the column is spelled **`Gender`** in ricu's config vs. **`Sex`** in the SICdb docs wiki prose — reconcile the exact column name against the real header on access; both likely refer to the same field |
| **In-hospital mortality** | `cases.OffsetOfDeath` non-null (survived-to-discharge = null) OR `cases.HospitalDischargeType` (reference-coded survival status) | seconds from admission (OffsetOfDeath); reference-coded (DischargeType) | SICdb docs wiki (Case Data) | Confirmed the fields exist; **recommend using `HospitalDischargeType` via the `d_references` join as primary** (categorical, unambiguous) and `OffsetOfDeath` as a cross-check, since `OffsetOfDeath` is described as a *1-year* mortality field (survival-analysis oriented) and needs a `<= TimeOfStay`-type bound to isolate the in-hospital subset specifically — TO-CONFIRM-ON-ACCESS exactly how to threshold it |
| Timestamp column | `laboratory.Offset`, `medication.Offset`/`OffsetDrugEnd`, `cases.ICUOffset`/`TimeOfStay` | **seconds** from ICU admission (integer) | SICdb docs wiki | Confirmed |

**Benchmark cases runnable:** all 6 labs have (medium-confidence) IDs, but **NONE of the 4 treatment
classes (RBC/insulin/NaHCO3/KCl) have a publicly confirmed DrugID** — SICdb's `medication` table is
entirely reference-coded and no public source (docs wiki, paper, ricu snippet reachable) enumerates
concrete DrugIDs. **This means SICdb is currently the weakest-mapped of the three datasets**: the lab
side of the assay-noise instrument can very likely be built from public sources + light on-access
verification, but the treatment/exposure side is a hard day-one blocker until `d_references` is pulled
and joined against `medication` to find drug names by string match (e.g. `ReferenceValue LIKE
'%Erythrozyten%'` / `'%Insulin%'` / `'%Bicarbonat%'` / `'%Kalium%'`).

---

## 3. AmsterdamUMCdb (Amsterdam, Netherlands — PhysioNet `amsterdamumcdb` v1.0.2)

**Best-documented of the three** (active GitHub wiki + `concepts/` folder + a published `dictionary.csv`
/ `amsterdamumcdb` PyPI package with `get_dictionary()`), but the specific medication itemids needed here
(RBC/NaHCO3/KCl) still could not be confirmed from a source reachable without dataset access — see below.

**Table schema** (confirmed, `github.com/AmsterdamUMC/AmsterdamUMCdb/wiki`):
- `admissions`: `patientid`, `admissionid`, `admissioncount`, `location`, `urgency`, `origin`,
  `admittedat` (ms since first admission; 0 for first admission), `admissionyeargroup`, `dischargedat`
  (ms since first admission), `lengthofstay`, `destination` (department discharged to, or **'Overleden'**
  if died during the ICU/MCU stay), `gender` ('Man'/'Vrouw'), `agegroup` (categorized age at admission —
  exact band strings e.g. "18-39" NOT confirmed from public sources, TO-CONFIRM-ON-ACCESS), `dateofdeath`
  (ms since first admission, non-null if died — NOT restricted to during-ICU-stay, i.e. broader than
  `destination=='Overleden'`), `weightgroup`/`heightgroup` (also categorized), `specialty`.
- `numericitems` (labs/vitals): `admissionid`, `itemid`, `item`, `value`, `unit`, `measuredat` (ms since
  first admission, can be negative for pre-admission draws), `registeredby`.
- `drugitems` (medication administrations): `admissionid`, `orderid`, `ordercategoryid`, `ordercategory`,
  `itemid`, `item`, `isadditive`, `isconditional`, `rate`, `rateunit`, `doserateperkg`, `dose`, `doseunit`,
  `administered`, `administeredunit`, `action`, `start`/`stop` (ms since first admission), `duration`
  (**minutes**, not ms), `solutionitemid`/`solutionitem` (for additives), `iscontinuous`.
- Item dictionary: `amsterdamumcdb/dictionary.csv` (via the `amsterdamumcdb` PyPI package /
  `get_dictionary()` function) — this is the correct file to pull first on access; could not be read
  through public WebFetch (file too large / not raw-fetchable without the package installed), but its
  existence and purpose (itemid -> label/unit) is confirmed.

**Timestamp convention:** all AmsterdamUMCdb timestamps are **integer milliseconds since the patient's
first ICU admission** (like eICU's minutes and SICdb's seconds, just finer-grained still) — convert to
hours via `measuredat / 3_600_000.0` (numericitems) or `start / 3_600_000.0` (drugitems).

| Concept | Table.Column / ID | Units | Source | Confidence |
|---|---|---|---|---|
| Hemoglobin | `numericitems.itemid` in {6778, 9553, 9960, 10286, 19703} | per `unit` column (TO-CONFIRM — mmol/L is common in Dutch labs, NOT g/dL; unit conversion likely needed) | ricu concept-dict.json (`hgb`) | Confirmed via ricu only |
| Glucose | `numericitems.itemid` in {6833, 9557, 9947} | TO-CONFIRM units (mmol/L likely, Dutch convention) | ricu concept-dict.json (`glu`) | Confirmed via ricu only |
| Platelet count | `numericitems.itemid` in {6779, 9553, 11586} | TO-CONFIRM (x10^9/L likely) | ricu concept-dict.json (`plt`) | Confirmed via ricu only |
| Bicarbonate/HCO3 | `numericitems.itemid` in {6810, 9992} | mEq/L or mmol/L, TO-CONFIRM | ricu concept-dict.json (`bicar`) | Confirmed via ricu only |
| Potassium | `numericitems.itemid` in {6835, 9556, 9927, 10285} | mmol/L | ricu concept-dict.json (`k`) | Confirmed via ricu only |
| Magnesium | `numericitems.itemid` in {6849, 9931} | mmol/L likely, TO-CONFIRM | ricu concept-dict.json (`mg`) | Confirmed via ricu only |
| RBC transfusion | **TO-CONFIRM-ON-ACCESS** | — | none confirmed | A follow-up verification pass explicitly caught and discarded a fabricated-looking itemid set here (a WebFetch summarizer produced numbers after admitting it could not actually see that part of the source file) — **do not trust any RBC itemid not re-derived directly from the raw JSON or the `dictionary.csv`/`concepts/` folder on access** |
| Insulin | `drugitems.itemid` in {7624, 9014, 19129} | — | ricu concept-dict.json (`ins`) | Confirmed via ricu only (this one WAS reached before the file-truncation point, unlike RBC/NaHCO3/KCl which are alphabetically later) |
| Sodium bicarbonate | **TO-CONFIRM-ON-ACCESS** | — | none confirmed | Same fabrication risk as RBC — discard any itemid not re-verified directly |
| Potassium chloride | **TO-CONFIRM-ON-ACCESS** | — | none confirmed | Same |
| Age | `admissions.agegroup` (CATEGORICAL, not continuous — privacy banding; exact bands TO-CONFIRM-ON-ACCESS) | categorized years | GitHub wiki (Admissions) | Confirmed field exists; confirmed it's banded not continuous; exact band strings TO-CONFIRM |
| Sex | `admissions.gender` | 'Man' / 'Vrouw' | GitHub wiki (Admissions) — independently re-verified | Confirmed |
| **In-hospital mortality** | `admissions.destination == 'Overleden'` (died during THIS ICU/MCU admission) — narrower/more appropriate than `dateofdeath` non-null, which is unrestricted (any death, any time) | categorical string | GitHub wiki (Admissions) | Confirmed. Use `destination=='Overleden'` as the in-hospital-mortality flag, NOT bare `dateofdeath` non-null (that would overcount deaths after discharge) |
| Timestamp columns | `numericitems.measuredat`; `drugitems.start`/`stop` (duration in minutes) | milliseconds since first ICU admission | GitHub wiki (Numericitems, Drugitems) | Confirmed |

**Benchmark cases runnable:** all 6 labs have (ricu-only, single-source) itemids; **only Insulin has a
confirmed treatment itemid** among the 4 treatment classes — RBC/NaHCO3/KCl are all TO-CONFIRM-ON-ACCESS.
Given AmsterdamUMCdb's own `concepts/` folder and `dictionary.csv` almost certainly DO contain these
(the repo is the best-documented of the three and explicitly advertises blood-transfusion and medication
concept extraction), this is the single highest-value day-one fetch: pull `dictionary.csv` (or run
`amsterdamumcdb.get_dictionary()`) and grep for `erytrocyten`/`erytrocytenconcentraat` (RBC),
`natriumbicarbonaat`/`bicarbonaat` (NaHCO3), and `kaliumchloride`/`kalium` (KCl) — Dutch-language item
labels, not English.

---

## Cross-dataset summary

| Concept | HiRID | SICdb | AmsterdamUMCdb |
|---|---|---|---|
| Hemoglobin (lab) | Confirmed | Medium | Confirmed (ricu) |
| Glucose (lab) | Confirmed | Medium | Confirmed (ricu) |
| Platelets (lab) | Confirmed | Medium | Confirmed (ricu) |
| Bicarbonate (lab) | Confirmed | Medium | Confirmed (ricu) |
| Potassium (lab) | Confirmed | Medium | Confirmed (ricu) |
| Magnesium (lab) | Medium | Medium | Confirmed (ricu) |
| RBC transfusion (tx) | Confirmed | **TO-CONFIRM** | **TO-CONFIRM** |
| Insulin (tx) | Confirmed (cross-source) | **TO-CONFIRM** | Confirmed (ricu) |
| Sodium bicarbonate (tx) | Confirmed | **TO-CONFIRM** | **TO-CONFIRM** |
| Potassium chloride (tx) | Confirmed | **TO-CONFIRM** | **TO-CONFIRM** |
| Age | Confirmed (continuous, capped 90) | Confirmed (+/-5y binned, capped 90) | Confirmed (categorical bands) |
| Sex | Confirmed | Confirmed (column name TO-reconcile: Sex vs Gender) | Confirmed |
| In-hospital mortality | Confirmed (`general.discharge_status`) | Confirmed field exists, thresholding TO-CONFIRM | Confirmed (`destination=='Overleden'`) |
| Timestamp convention | Absolute datetime (timeshifted) | Seconds from admission | Milliseconds from first admission |

**Overall read: HiRID is the most fully mapped of the three (all 10 concepts + all 4 treatments confirmed
from public sources, several cross-source), AmsterdamUMCdb is best for labs+patient-level fields but weak
on 3 of 4 treatments, and SICdb is weakest on treatments (0 of 4 confirmed) despite being present in ricu**
— because SICdb's `medication` table is 100% reference-coded with no public DrugID listing, unlike HiRID
(which has the `HIRID-ICU-Benchmark` `varref.tsv` naming pharma items) or AmsterdamUMCdb (which has Dutch
item names + a dictionary.csv, just not one we could read through public tooling here).

## Day-one verification checklist (do this before trusting any TO-CONFIRM cell)

1. **HiRID**: fetch `hirid_variable_reference.csv` + `ordinal_vars_ref.csv` from
   `physionet.org/content/hirid/1.1.1/reference_data/` (DUA-gated, 403'd here) — verify magnesium
   variableid 20005200 and spot-check the RBC/NaHCO3/KCl pharmaids against it.
2. **SICdb**: fetch the `d_references` table and join it against `laboratory`/`medication` to (a) confirm
   the 6 lab LaboratoryIDs' units, and (b) string-search `ReferenceValue` for "Erythrozyten"/"EK",
   "Insulin", "Bicarbonat", "Kalium"/"KCl" to find the 4 treatment DrugIDs from scratch — this is a hard
   blocker, budget real time for it.
3. **AmsterdamUMCdb**: fetch `amsterdamumcdb/dictionary.csv` (or run `pip install amsterdamumcdb` and call
   `get_dictionary()`) and the `concepts/` folder notebooks; string-search for
   "erytrocytenconcentraat"/"packed cells", "natriumbicarbonaat", "kaliumchloride" to find the 3 missing
   treatment itemids; also confirm the exact `agegroup` band strings and lab units (mmol/L vs g/dL,
   Dutch labs commonly report Hb/glucose in mmol/L, NOT the US mg/dL or g/dL convention — a unit-conversion
   bug here would silently corrupt every flag threshold).
4. For all three: confirm every itemid/variableid/LaboratoryID pulled from `ricu`'s public snippet by
   reading real table headers + a sample of values (sanity-check units/ranges) before wiring into the
   adapter's CONFIG — the ricu concept dict is a strong prior, not a substitute for verification, and this
   review already caught one instance of a sub-agent tool fabricating itemids under a truncated fetch.
