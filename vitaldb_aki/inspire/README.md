# INSPIRE External-Validation Stage

INSPIRE (doi:10.13026/93f2-3t63, PhysioNet v1.4.2) is a restricted-access dataset
of ~130k SNUH surgeries (2011–2020) with EHR data at 1–5-minute resolution.
It is the external-validation cohort for the distilled **PFDS-Clinical** biomarker.

---

## Access gating

| Step | Action |
|------|--------|
| 1. PhysioNet account | Register at https://physionet.org/register/ |
| 2. DUA | Open https://physionet.org/content/inspire/1.4.2/ and click "Request Access" |
| 3. DUA approval | Typically 24–72 hours |
| 4. Download | `wget -r -N -c -np --user <user> --password <pass> https://physionet.org/files/inspire/1.4.2/` |
| 5. Set env var | `export INSPIRE_DATA_DIR=/path/to/inspire/1.4.2/` |

No credential is committed to this repository.  The code never initiates a
network connection to PhysioNet — all I/O is local file reading.

---

## VitalDB ↔ INSPIRE variable-overlap table

| Clinical concept | VitalDB column | INSPIRE column | Notes |
|---|---|---|---|
| **MAP** | Solar8000/ART_MBP or NIBP_MBP (500 Hz → epoch mean) | vitals.csv `mbp` | INSPIRE @ 5 min; VitalDB sub-second |
| **Heart rate** | Solar8000/HR or PLETH_HR | vitals.csv `hr` | Same concept; different resolution |
| **SpO2** | Solar8000/PLETH_SPO2 | vitals.csv `spo2` | |
| **EtCO2** | Solar8000/ETCO2 | vitals.csv `etco2` | Key perfusion surrogate |
| **FiO2** | Primus/FIO2 or Fabius/FIO2 | vitals.csv `fio2` | Unit may differ (fraction vs %); normalised in code |
| **Vent tidal volume** | Primus/TV or Fabius/TV | vitals.csv `tv` | |
| **PEEP** | Primus/PEEP or Fabius/PEEP | vitals.csv `peep` | |
| **Temperature** | Solar8000/TEMP | vitals.csv `temp` | |
| **Vasopressors** | Pump tracks (rate+Ce, 500 Hz) | medications.csv (dose/time events) | VitalDB: continuous infusion; INSPIRE: episodic records |
| **Anesthetic agent** | Propofol pump Ce; volatile MAC tracks | medications.csv + vitals etco2/fio2 | Reduced fidelity in INSPIRE |
| **Creatinine (preop)** | /labs `cr`, dt < 0 | labs.csv `cr`, time < 0 | Identical concept |
| **Creatinine (postop)** | /labs `cr`, dt > opend | labs.csv `cr`, time > opend | Identical concept |
| **Age** | cases.csv `age` | operations.csv `age` | |
| **Sex** | cases.csv `sex` | operations.csv `sex` | |
| **ASA class** | cases.csv `asa` | operations.csv `asa` | |
| **Emergency flag** | cases.csv `emop` | operations.csv `emergency` | Column name differs |
| **Surgery type** | cases.csv `optype` | operations.csv `optype` | Category labels may differ |
| **Surgery duration** | opend − opstart (seconds) | opend − opstart (seconds) | |
| **ICU LOS** | Not available | operations.csv `icu_days` | INSPIRE only |
| **Hospital LOS** | Not available | operations.csv `hosp_days` | INSPIRE only |
| **In-hospital mortality** | cases.csv `death_inhosp` | operations.csv `inhosp_death` | Column name differs |
| **CRRT** | Not available | operations.csv `crrt` | INSPIRE only |
| **ECMO** | Not available | operations.csv `ecmo` | INSPIRE only |
| **BMI / height / weight** | cases.csv `bmi`, `height`, `weight` | operations.csv `bmi`, `height`, `weight` | |
| **Baseline creatinine** | /labs preop cr | labs.csv preop cr | Derived identically |
| **Troponin** | NOT in VitalDB open set | labs.csv -- coverage incomplete | Verify on real data |
| **Lactate** | /labs `lac` | labs.csv `lac` | May have poor postop coverage |
| **Pump-effect-site Ce** | Propofol/remi tracks | NOT available in INSPIRE | Waveform model only |
| **500 Hz waveforms** | Available (ART/pleth/ECG) | NOT available | Clinical model only |

---

## What runs once data is present

```bash
export INSPIRE_DATA_DIR=/data/inspire/1.4.2

# 1. Sanity check
python -c "from vitaldb_aki.inspire.client import available; print(available())"

# 2. Compute labels + features
python - <<'EOF'
from vitaldb_aki.inspire.client import load_table
from vitaldb_aki.inspire.labeling import label_all_cases
from vitaldb_aki.inspire.pfds_clinical import compute_pfds_clinical_all

ops  = load_table("operations")
labs = load_table("labs")
vits = load_table("vitals")
meds = load_table("medications")

labels   = label_all_cases(ops, labs)
features = compute_pfds_clinical_all(ops, vits, meds)
EOF

# 3. External validation (after VitalDB PFDS-Clinical model is frozen)
python - <<'EOF'
# Load frozen model (hash-verified) and run validate()
from vitaldb_aki.inspire.validate import validate
# ... (see validate.py docstring)
EOF
```

---

## Required INSPIRE tables and columns

| Table | Required columns |
|-------|-----------------|
| operations.csv | caseid, subjectid, opstart, opend, age, sex, asa, emergency, optype, bmi, inhosp_death, icu_days, hosp_days, crrt, ecmo |
| vitals.csv | caseid, time, mbp, hr, spo2, etco2, fio2, rr, tv, peep, temp |
| labs.csv | caseid, time, name, result (where name='cr') |
| medications.csv | caseid, time, name, amount, unit |

Verify actual column names against the downloaded header rows before running.
Update `COLUMN_MAP` in `pfds_clinical.py` if they differ from the above.

---

## Pre-registration note

Per STRATEGY_PFDS.md: the PFDS-Clinical biomarker definition (CLINICAL_COMPUTABLE
in `pfds_clinical.py`) must be FROZEN and hash-pinned before any INSPIRE outcome
data is accessed.  The labeling + feature code may be run on INSPIRE (no outcome
peeking: labels are computed from creatinine data, which is independent of the
biomarker features).  The `validate()` function must only be called after the
model checkpoint is frozen.
