#!/usr/bin/env python3
"""Extract a random sample of HEEDB strict-normal recordings, to test the ONE hypothesis that could
justify the full reference build.

WHY THIS EXISTS, AND WHY IT IS A SAMPLE RATHER THAN THE COHORT.
`bsde/docs/REFERENCE_VALUE_MEASURED.md` measured what the conditional reference buys and found it small:
the best gain anywhere is 1.083 (E54, awake adults, age + sex), and Challenge B's own marker gains 1.000.
On that evidence the full build -- wake detector, eye-state detector, signal pass over 4,944 recordings,
freezing and hashing -- is not justified.

**One hypothesis survives and it is specific.** Every deposit measured so far carries only AGE and SEX.
`NORMAL_REFERENCE_COVARIATES.md` §2 argues the covariates that matter are MEDICATION and COMORBIDITY --
88.9 % of this cohort carries nervous-system drugs, and no existing normative database corrects for
medication at all. If those explain substantially more variance than age and sex, the arithmetic changes
and the build is justified. If they explain comparably little, it is not.

That question needs a SAMPLE, not the cohort, and no frozen artefact. This script takes one.

=========================================================================================================
DESIGN DECISIONS, EACH FIXED HERE BEFORE ANY FEATURE VALUE EXISTS
=========================================================================================================
RANDOM SAMPLE, NOT STRATIFIED, AND THIS IS THE SUBTLE ONE. The obvious design over-samples the 551
patients with no nervous-system drug to maximise contrast. **That would bias the answer toward the
conclusion we are testing for**: R^2 depends on the covariate's variance in the sample, so inflating the
rarity of an exposure inflates its R^2. A random sample keeps every covariate at its natural prevalence,
which is the only way the comparison against age and sex is fair. The 14 ATC chapters run at 44-64 %
prevalence anyway, so a random sample carries ample medication variance without any stratification.

RESTRICT TO `Routine` SERVICE, per `NORMAL_REFERENCE_COVARIATES.md` §3 -- LTM and EMU are an
epilepsy-workup population with different acquisition. 4,192 of 4,944 qualify.

THE 180 s WINDOW STARTS AT 300 s. HEEDB recordings run 1,344-3,989 s, so a byte-range prefix of the EDF
gives roughly a 20x transfer reduction -- but the FIRST minutes of a routine EEG are calibration, electrode
settling and instructions, not resting state. Starting at 300 s skips that. **This is a fixed, declared,
arbitrary choice and it is NOT a substitute for the vigilance detector**: 94.8 % of these recordings
contain sleep and Q21 established the metadata cannot locate it. What makes the choice tolerable HERE and
nowhere else is that this experiment compares covariate blocks AGAINST EACH OTHER within the same noisy
data, and vigilance noise inflates the residual for every block alike. It would not be tolerable for
estimating an absolute normative value.

EDF PREFIX FETCH. Header gives `ns`, `nrecords` and record duration; bytes for the wanted span are
range-fetched and **`nrecords` is patched in the local copy** to the number of records actually present,
because a truncated EDF whose header still claims the original length is a malformed file that readers
handle inconsistently. Verified against a full download in the smoke test.

    scripts/heedb_run.sh python analysis/heedb_reference_sample.py --n 600
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import random
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "bsde", "src"))
from common.awsenv import sanitize as _aws_sanitize                          # noqa: E402
from eeg_features_common import features_from_file, ANALYSIS_S               # noqa: E402

AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
MED = "EEG/HEEDB_Metadata/HEEDB_Medication_ATC.csv"
COHORT = "/tmp/eeg_probe/heedb_normal_reference.csv"
START_S = 300.0
SEED = 20260731


def _s3():
    _aws_sanitize(verbose=False)
    import boto3
    from botocore.config import Config
    try:
        sess = boto3.Session(profile_name="physionet")
        sess.client("sts").get_caller_identity()
    except Exception:                                                        # noqa: BLE001
        sess = boto3.Session()
    return sess.client("s3", region_name="us-east-1",
                       config=Config(s3={"payload_signing_enabled": False}))


def _edf_prefix(cl, key, out_path, start_s=START_S, span_s=None):
    """Fetch only the records covering [start_s, start_s+span_s) and patch `nrecords`.

    A truncated EDF whose header still declares the original record count is malformed; readers either
    error or fabricate. Patching the count makes the local file internally consistent.
    """
    span_s = span_s or (ANALYSIS_S + 2.0)
    head = cl.get_object(Bucket=AP, Key=key, Range="bytes=0-255")["Body"].read()
    hdr_bytes = int(head[184:192].decode().strip())
    nrec = int(head[236:244].decode().strip())
    rec_dur = float(head[244:252].decode().strip())
    ns = int(head[252:256].decode().strip())
    full = cl.get_object(Bucket=AP, Key=key, Range=f"bytes=0-{hdr_bytes - 1}")["Body"].read()
    # samples-per-record for each signal sit in the last ns*8 bytes of the header
    spr = [int(full[hdr_bytes - ns * 8 + i * 8: hdr_bytes - ns * 8 + (i + 1) * 8].decode().strip())
           for i in range(ns)]
    rec_size = sum(spr) * 2
    if rec_dur <= 0 or rec_size <= 0:
        raise RuntimeError("unusable EDF header")
    first = int(start_s // rec_dur)
    want = int(span_s / rec_dur) + 1
    if first + want > nrec:                       # not enough record after the offset: fall back to start
        first, want = 0, min(want, nrec)
    lo = hdr_bytes + first * rec_size
    hi = lo + want * rec_size - 1
    body = cl.get_object(Bucket=AP, Key=key, Range=f"bytes={lo}-{hi}")["Body"].read()
    got = len(body) // rec_size
    if got < 1:
        raise RuntimeError("no complete record fetched")
    patched = bytearray(full)
    patched[236:244] = f"{got:<8d}".encode()
    with open(out_path, "wb") as fh:
        fh.write(bytes(patched))
        fh.write(body[:got * rec_size])
    return got * rec_dur


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="/tmp/eeg_probe/heedb_reference_sample.csv")
    ap.add_argument("--n", type=int, default=600)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args(argv)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    cl = _s3()

    with open(COHORT) as fh:
        cohort = [r for r in csv.DictReader(fh)
                  if r["service"] == "Routine" and r["bids_folder"]]
    print(f"Routine strict-normal with a BidsFolder: {len(cohort)}", flush=True)

    med_raw = cl.get_object(Bucket=AP, Key=MED)["Body"].read().decode("utf-8", "replace")
    med_rows = list(csv.DictReader(io.StringIO(med_raw)))
    med_cols = [c for c in med_rows[0]
                if c not in ("BDSPPatientID", "SiteID", "SexDSC", "VisitCount", "AgeAtVisitAvg")]
    med = {r["BDSPPatientID"]: r for r in med_rows}
    print(f"medication table: {len(med_rows)} patients, {len(med_cols)} ATC chapters", flush=True)

    rng = random.Random(SEED)
    pool = sorted(cohort, key=lambda r: (r["site"], r["patient_id"], r["session_id"]))
    rng.shuffle(pool)
    pool = pool[:a.n]

    done = set()
    if os.path.exists(a.out):
        with open(a.out) as fh:
            done = {(r["site"], r["patient_id"], r["session_id"]) for r in csv.DictReader(fh)}
        print(f"resuming: {len(done)} present", flush=True)

    fh_out = w = None
    n_ok = n_fail = 0
    t0 = time.time()
    for r in pool:
        key3 = (r["site"], r["patient_id"], r["session_id"])
        if key3 in done:
            continue
        pre = f"EEG/bids/{r['site']}/{r['bids_folder'].strip('/')}/"
        try:
            listing = cl.list_objects_v2(Bucket=AP, Prefix=pre, MaxKeys=60).get("Contents", [])
            edfs = [o["Key"] for o in listing if o["Key"].endswith("_eeg.edf")]
            if not edfs:
                raise RuntimeError("no EDF under this BidsFolder")
            key = sorted(edfs)[0]
            tmp = tempfile.NamedTemporaryFile(suffix=".edf", delete=False)
            tmp.close()
            _edf_prefix(cl, key, tmp.name)
            feats = features_from_file(tmp.name)
        except Exception as exc:                                             # noqa: BLE001
            n_fail += 1
            print(f"   FAIL {r['patient_id']}: {type(exc).__name__}: {exc}", flush=True)
            continue
        finally:
            try:
                os.unlink(tmp.name)
            except Exception:                                                # noqa: BLE001
                pass
        m = med.get(r["patient_id"], {})
        row = {"site": r["site"], "patient_id": r["patient_id"], "session_id": r["session_id"],
               "age": r["age_at_visit"], "sex": r["sex"],
               "n_icd_chapters": r["n_icd_chapters"], "edf_key": key.split("/")[-1]}
        for c in med_cols:
            row["atc_" + c.split()[0].lower().strip(",")] = 1 if (m.get(c) or "").strip() else 0
        for c in r:
            if c.startswith("icd_"):
                row[c] = r[c]
        row.update(feats)
        if w is None:
            fh_out = open(a.out, "a", newline="")
            w = csv.DictWriter(fh_out, fieldnames=list(row.keys()))
            if os.path.getsize(a.out) == 0:
                w.writeheader()
        w.writerow(row)
        fh_out.flush()
        n_ok += 1
        if n_ok % 20 == 0:
            el = time.time() - t0
            print(f"   {n_ok} ok / {n_fail} fail   {el/n_ok:.1f}s each   "
                  f"eta {(len(pool)-n_ok)*el/n_ok/60:.0f} min", flush=True)
        if a.limit and n_ok >= a.limit:
            break
    print(f"\n{n_ok} written, {n_fail} failed -> {a.out}")
    print("NOT committed: credentialed patient-derived data lives under /tmp/eeg_probe only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
