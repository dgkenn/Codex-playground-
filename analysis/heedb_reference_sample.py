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

THE 180 s WINDOW IS SEARCHED FOR, NOT FIXED -- and the first version got this wrong. HEEDB recordings run 1,344-3,989 s, so a byte-range prefix of the EDF
gives roughly a 20x transfer reduction (measured: 2.2 MB against 48.3 MB, 21.7x). The first version took
a fixed window at 300 s, on the reasoning that the opening minutes are calibration and electrode settling.
**That failed on 100 % of recordings and the failure was in the DATA, not the code.** A HEEDB routine EEG
contains long DISCONNECTED stretches: on the first cohort recording, every channel is railed at the
physical minimum and perfectly constant at t = 300 s, 600 s and 1200 s, while carrying real EEG at t = 0 s
(std 462/310/254 uV) and t = 2400 s (std 34/24/107 uV). The record-size arithmetic was correct throughout
-- 12,114 bytes, matching the file size exactly -- so nothing about the prefix fetch was at fault.

So the window is now SEARCHED: candidate offsets are tried in order and the first whose median channel
amplitude falls in a plausible EEG range is kept. **This is a quality gate and it is declared as one.** It
is applied blind to every covariate, and the offset actually used is emitted as a column (`window_start_s`)
so that any relationship between artefact burden and medication or comorbidity is CHECKABLE rather than
hidden -- which matters, because sicker patients plausibly have more artefact, and that would be a
confound running in exactly the direction of the hypothesis under test.

**It is NOT a substitute for the vigilance detector**: 94.8 % of these recordings
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
SEARCH_OFFSETS_S = (300.0, 600.0, 900.0, 1200.0, 1800.0, 2400.0, 3000.0, 60.0)
"""Offsets tried in order. 60 s is LAST rather than first: the opening minute is calibration and electrode
settling, so it is the fallback only when nothing later is usable."""
AMP_LO_UV, AMP_HI_UV = 3.0, 300.0
"""Median across the montage of per-channel SD, in microvolts. Below 3 is a disconnected or railed
segment; above 300 is movement, electrode pop or calibration. Both bounds are conventional rather than
tuned, and they are applied identically to every recording."""
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
    # SAMPLES-PER-RECORD IS THE SECOND-TO-LAST HEADER FIELD, NOT THE LAST. After the fixed 256-byte
    # header EDF stores, per signal: label 16, transducer 80, physical dimension 8, physical min 8,
    # physical max 8, digital min 8, digital max 8, prefiltering 80 -> 216 bytes, THEN samples-per-record
    # 8, THEN reserved 32. Total 256 + ns*256, which is why `hdr_bytes - ns*8` looks right and is not:
    # it lands inside the trailing ns*32 reserved block, which is blank, and every parse raised
    # int('') on an empty string. Caught by the smoke test failing on 100 % of recordings.
    off = 256 + ns * 216
    spr = [int(full[off + i * 8: off + (i + 1) * 8].decode().strip()) for i in range(ns)]
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


def _first_usable_window(cl, key, out_path):
    """Try each offset in `SEARCH_OFFSETS_S` and keep the first with plausible EEG amplitude.

    Returns the offset used. Raises if none qualifies, so an all-artefact recording becomes a counted
    FAIL rather than a row of noise (rule 5)."""
    import mne
    import numpy as np
    from eeg_features_common import MONTAGE
    last = None
    for start in SEARCH_OFFSETS_S:
        try:
            _edf_prefix(cl, key, out_path, start_s=start)
            raw = mne.io.read_raw_edf(out_path, preload=True, verbose="ERROR")
            want = {c.lower() for c in MONTAGE}
            keep = [c for c in raw.ch_names if c.lower() in want]
            if not keep:
                raise RuntimeError(f"none of {MONTAGE} present")
            raw.pick(keep)
            sd = float(np.median(np.std(raw.get_data() * 1e6, axis=1)))
            last = sd
            if AMP_LO_UV <= sd <= AMP_HI_UV:
                return start
        except Exception:                                                    # noqa: BLE001
            continue
    raise RuntimeError(f"no window with plausible amplitude (last median SD {last})")


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
            used = _first_usable_window(cl, key, tmp.name)
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
               "n_icd_chapters": r["n_icd_chapters"], "edf_key": key.split("/")[-1],
               "window_start_s": used}
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
