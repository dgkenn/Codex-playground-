#!/usr/bin/env python3
"""Extract the OMOP clinical record for HEEDB patients with clinician-labelled BURST SUPPRESSION.

WHY THIS COHORT EXISTS. Guay, Agrawal, Tseng, Gallo, Schreier and Brown, in "Clinical Electroencephalography for
Anesthesiologists and Intensivists: Part 2" (Anesthesiology 2025;143(6):1595-1618), state three open problems
verbatim:

    "Determining the exact etiology of burst suppression in the ICU can be challenging and likely contributes to
     heterogeneous results in clinical outcomes studies."

    "Future work characterizing distinct burst suppression phenotypes and the underlying mechanisms will help
     refine our understanding of this brain state."

    "Future studies investigating the use of continuous frontal EEG in critically ill patients will provide new
     insights into the bidirectional interactions between the brain and the rest of the body."

HEEDB plus its OMOP linkage is unusually well suited to the first two. The cohort is 7,323 patients with burst
suppression labelled on 22,057 EEG reports, overwhelmingly from long-term (ICU continuous) monitoring, and patient
identifiers link to the OMOP common data model at 100 % — verified by matching all 34,620 site-S0001 EEG patients
against the 15M-row person table. Published burst-suppression phenotyping studies are typically in the hundreds of
patients.

WHAT IS PULLED, and why each matters for the aetiology question:
    condition_occurrence  diagnoses (ICD-9/10 source values) -- the aetiology substrate itself: anoxic injury,
                          status epilepticus, sepsis, hepatic and renal failure, intoxication, hypothermia
    drug_exposure         sedative and anaesthetic exposure -- separates IATROGENIC suppression (propofol,
                          midazolam, pentobarbital, ketamine) from suppression arising from injury or metabolic
                          derangement. This is the single most important discriminator, and it is exactly what
                          makes ICU aetiology "challenging" when only the EEG is available.
    measurement           vital signs and labs -- the brain-body coupling variables, plus severity markers
    death                 mortality outcome (available for 3,304 of the 7,323, 45 %)

DESIGN NOTE. This script only EXTRACTS. Phenotyping and any outcome analysis are separate, so that the cohort can
be built once and analysed under a pre-specified plan rather than assembled and modelled in the same pass.

SCALE AND METHOD. The merged OMOP tables are large (measurement 66 GB / 554 files, drug_exposure 59 GB / 375,
condition_occurrence 27 GB / 181). Each Parquet part is streamed, filtered to the target patient set, and
discarded; only matching rows are written. Roughly 0.4 % of rows match, so the outputs are manageable. The script
is resumable at file granularity via a manifest, because a run of this length will be interrupted.
"""
import argparse, io, json, os, re, sys, time
from collections import defaultdict

import boto3
from botocore.config import Config
import pyarrow.parquet as pq

AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
OUT = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
PIDS_FILE = os.environ.get("PIDS_FILE", "/tmp/heedb_bs_patients.txt")

# columns kept per table: enough to phenotype and to time-align, nothing more
COLS = {
    "condition_occurrence": ["person_id", "condition_start_datetime", "condition_concept_id",
                             "condition_source_value"],
    "drug_exposure": ["person_id", "drug_exposure_start_datetime", "drug_exposure_end_datetime",
                      "drug_concept_id", "drug_source_value", "quantity"],
    "measurement": ["person_id", "measurement_datetime", "measurement_concept_id",
                    "measurement_source_value", "value_as_number", "unit_source_value"],
    "death": ["person_id", "death_datetime", "cause_source_value"],
    # Consciousness assessments, for the recovery-of-consciousness arm. Same physical table as `measurement`,
    # but ROW-FILTERED: the merged measurement table is 66 GB / 554 parts and holds every lab and vital sign, so
    # pulling it whole for 49k patients would produce tens of GB of mostly-irrelevant chemistry. Filtering on the
    # source value at extraction keeps the output small enough to analyse in memory.
    "measurement_conscious": ["person_id", "measurement_datetime", "measurement_concept_id",
                              "measurement_source_value", "value_as_number", "unit_source_value"],
    # Sedatives only, for the recovery-of-consciousness arm. The existing drug_exposure.csv was extracted
    # against the 7,323-patient burst-suppression cohort, so it has NO BS-negative comparison group -- using it
    # for the RoC study would silently restrict the model to BS-positive patients, which is exactly the failure
    # that produced a false "D1 FALSIFIED" in the dose-response test. This pulls the full 49,232-patient EEG
    # cohort, and row-filters to the sedative classes the analysis names so the output stays small.
    "drug_sedatives": ["person_id", "drug_exposure_start_datetime", "drug_exposure_end_datetime",
                       "drug_concept_id", "drug_source_value", "quantity"],
    # Vasopressors, for dating ACUTE withdrawal of life-sustaining therapy. The DNR/palliative codes turned out
    # to be a blunt proxy -- median 42 days from code to death, only 5 % dying within a day -- because they
    # document chronic care-limitation status rather than an acute decision. Stopping a vasopressor in a
    # pressor-dependent patient is followed by death within hours, so the discontinuation TIME is a far sharper
    # marker of the decision. Needs drug_exposure_end_datetime, which this table carries.
    "drug_vasopressors": ["person_id", "drug_exposure_start_datetime", "drug_exposure_end_datetime",
                          "drug_concept_id", "drug_source_value", "quantity"],
    # ---- added 2026-07-26, to close the three open questions -------------------------------------------
    # PROCEDURES. Withdrawal-versus-refractory-shock has now defeated three instruments (DNR codes: chronic
    # status, median 42 d to death; sedation depth: circular; vasopressor end times: stamped AT death by the
    # charting system). All three failed the same way -- they are STATE tables, and the question is about a
    # DECISION. A terminal extubation is a decision with a timestamp, which is what this table records.
    "procedure_life_support": ["person_id", "procedure_datetime", "procedure_date", "procedure_concept_id",
                               "procedure_source_value"],
    # DISCHARGE DISPOSITION. A discharge to hospice, or an in-hospital death coded as comfort care, is an
    # explicit statement that the goal of care changed. Unlike a drug end-time it cannot be produced by a
    # record being closed automatically.
    "visit_disposition": ["person_id", "visit_start_datetime", "visit_end_datetime", "visit_concept_id",
                          "discharge_to_concept_id", "discharge_to_source_value", "visit_source_value"],
    # CODE STATUS / GOALS OF CARE, with a datetime. The earlier DNR work used condition_occurrence codes, which
    # document chronic status. The observation table carries the dated entries.
    "observation_goals": ["person_id", "observation_datetime", "observation_date", "observation_concept_id",
                          "observation_source_value", "value_as_string"],
    # NEURON-SPECIFIC ENOLASE, for what burden is a marker OF. NSE is the guideline-endorsed serum marker of
    # neuronal injury after cardiac arrest and sits alongside EEG in ERC-ESICM prognostication. If measured
    # suppression burden tracks NSE, burden is reading out neuronal loss; if it does not, it is reading out
    # something else, and either answer closes the mechanism question with an external reference rather than
    # an argument. S100B included as the secondary astroglial marker.
    "measurement_nse": ["person_id", "measurement_datetime", "measurement_date", "measurement_concept_id",
                        "measurement_source_value", "value_as_number", "unit_source_value"],
}

# pseudo-table -> the physical OMOP table it reads
SOURCE_TABLE = {"measurement_conscious": "measurement", "drug_sedatives": "drug_exposure",
                "drug_vasopressors": "drug_exposure", "procedure_life_support": "procedure_occurrence",
                "visit_disposition": "visit_occurrence", "observation_goals": "observation",
                "measurement_nse": "measurement"}

# pseudo-table -> (column to test, compiled regex a row must match to be kept)
ROW_FILTER = {"measurement_conscious": ("measurement_source_value",
                                        re.compile(r"glasgow|\bgcs\b|rass|richmond|sedation scale|"
                                                   r"level of consciousness|eye opening|best motor response|"
                                                   r"best verbal response|ramsay|arousal", re.I)),
               "drug_sedatives": ("drug_source_value",
                                  re.compile(r"propofol|midazolam|pentobarbital|thiopental|phenobarbital|"
                                             r"dexmedetomidine|precedex|lorazepam|ketamine", re.I)),
               "drug_vasopressors": ("drug_source_value",
                                     re.compile(r"norepinephrine|levophed|epinephrine|vasopressin|"
                                                r"phenylephrine|neosynephrine|dopamine|dobutamine|"
                                                r"angiotensin\s*II", re.I)),
               # Airway and life-support procedures. Word boundaries on the short tokens: a bare "cpr"
               # substring would also match unrelated free text.
               "procedure_life_support": ("procedure_source_value",
                                          re.compile(r"extubat|re-?intubat|\bintubat|mechanical ventilat|"
                                                     r"invasive ventilat|ventilator|tracheostom|\bcpr\b|"
                                                     r"cardiopulmonary resuscitat|\becmo\b|life support|"
                                                     r"withdraw|comfort care|palliat|hospice|terminal wean",
                                                     re.I)),
               "observation_goals": ("observation_source_value",
                                     re.compile(r"\bdnr\b|do not resuscitat|\bdni\b|do not intubat|"
                                                r"code status|full code|comfort|goals of care|\bpolst\b|"
                                                r"\bmolst\b|allow natural death|\bdnar\b|withdraw", re.I)),
               # \bnse\b matters here: an unbounded "nse" matches "response", "nonsense", "intense".
               "measurement_nse": ("measurement_source_value",
                                   re.compile(r"enolase|\bnse\b|s-?100", re.I))}


def client():
    return boto3.client("s3", region_name="us-east-1",
                        config=Config(s3={"payload_signing_enabled": False},
                                      retries={"max_attempts": 5, "mode": "standard"}))


def list_parts(s3, table):
    pg = s3.get_paginator("list_objects_v2")
    keys = []
    for page in pg.paginate(Bucket=AP, Prefix=f"OMOP/Merged/{table}/"):
        for o in page.get("Contents", []):
            if o["Key"].endswith(".parquet"):
                keys.append(o["Key"])
    return sorted(keys)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("table", choices=sorted(COLS))
    ap.add_argument("--limit", type=int, default=0, help="stop after N files (0 = all)")
    args = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    pids = {int(x) for x in open(PIDS_FILE).read().split() if x.strip().isdigit()}
    print(f"target patients: {len(pids)}", flush=True)

    s3 = client()
    keys = list_parts(s3, SOURCE_TABLE.get(args.table, args.table))
    manifest_path = f"{OUT}/{args.table}.done.json"
    done = set(json.load(open(manifest_path))) if os.path.exists(manifest_path) else set()
    todo = [k for k in keys if k not in done]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{args.table}: {len(keys)} parts, {len(done)} already done, {len(todo)} to do", flush=True)

    out_path = f"{OUT}/{args.table}.csv"
    new_file = not os.path.exists(out_path)
    fh = open(out_path, "a", newline="")
    import csv as _csv
    w = _csv.writer(fh)
    cols = COLS[args.table]
    if new_file:
        w.writerow(cols); fh.flush()

    t0 = time.time(); nrows = 0
    for i, key in enumerate(todo, 1):
        try:
            body = s3.get_object(Bucket=AP, Key=key)["Body"].read()
            have = pq.ParquetFile(io.BytesIO(body)).schema_arrow.names
            use = [c for c in cols if c in have]
            t = pq.read_table(io.BytesIO(body), columns=use)
            data = {c: t.column(c).to_pylist() for c in use}
            pid = data["person_id"]
            keep = [j for j, p in enumerate(pid) if p in pids]
            rf = ROW_FILTER.get(args.table)
            if rf:
                col, rx = rf
                vals = data.get(col)
                if vals is None:
                    raise KeyError(f"{col} absent from {key}; row filter cannot be applied safely")
                keep = [j for j in keep if vals[j] and rx.search(str(vals[j]))]
            for j in keep:
                w.writerow([data[c][j] if c in data else "" for c in cols])
            nrows += len(keep)
            fh.flush()
            done.add(key)
            json.dump(sorted(done), open(manifest_path, "w"))
        except Exception as e:
            print(f"  [{i}/{len(todo)}] FAILED {key.split('/')[-1][:40]}: {type(e).__name__} {str(e)[:90]}",
                  flush=True)
            continue
        if i % 10 == 0 or i == len(todo):
            el = time.time() - t0
            print(f"  [{i}/{len(todo)}] {nrows:,} rows kept  ({el/60:.1f} min, "
                  f"{i/max(el/60,1e-9):.1f} files/min)", flush=True)
    fh.close()
    print(f"DONE {args.table}: {nrows:,} rows -> {out_path}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
