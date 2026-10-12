#!/usr/bin/env python3
"""Build the NORMAL-READ reference cohort from HEEDB — the covariate-adjusted centroid.

WHY THIS EXISTS. `bsde/docs/UCE_AND_THE_THREE_CHALLENGES.md` §"what to learn" identifies the frozen
population reference as the one method the prior work has that this project does not, and the reason our
results do not compose across deposits: every experiment here normalises WITHIN cohort, which is why E39
could not combine `ds004541` and `chennu` into one estimate and why E36's legibilities cannot be carried
anywhere.

The prior work's reference was 1,170 BDSP **sleep-study** patients. That population is not healthy — it is
people referred for suspected sleep pathology — and it supplies a single global centroid, which is why the
operating point moved from -0.30 to -2.09 across individuals in the Purdon data.

**This builds a better one: routine clinical EEGs read as NORMAL by expert neurophysiologists, with the
reference conditioned on age, sex and comorbidity rather than pooled into one number.** A conditional
reference is the principled version of "use the patient's own awake baseline", and it has the property that
matters clinically: **it works where no baseline recording exists** — ICU, emergency, disorders of
consciousness — which is exactly where the flagship applications are.

WHAT COUNTS AS A NEGATIVE READ, AND WHY THE STRICT DEFINITION IS PRIMARY. The findings table carries a
`normal` column and ~40 per-finding columns. Two definitions are produced and the strict one is primary:

    loose   `normal` populated                       36,109 recordings across both sites
    STRICT  `normal` populated AND every abnormality  5,337 recordings, 4,918 patients
            column empty

The gap is large and it is not a rounding detail: a report can be summarised "normal" while an annotation
records focal slowing or a breach rhythm. **A reference centroid built from recordings that carry recorded
abnormalities is not a normal reference**, and the whole value of the object is that it is trustworthy.
The loose set is emitted too, as the sensitivity arm a reader will ask for.

COVERAGE, MEASURED BEFORE THIS SCRIPT WAS WRITTEN (metadata only, no signal touched):

    129,831 recordings in the findings tables (S0001 + S0002)
      5,337 STRICT normal
      4,918 unique patients, **100 % of them present in HEEDB_ICD10_for_Neurology.csv**
        age median 41, IQR 23-61, full range 0-90
        sex 2,472 F / 2,446 M
        comorbidity median 3 ICD chapters populated; 474 patients with none at all

That age range is what makes an age-conditional reference possible at all, and the 474 zero-comorbidity
patients give a clean inner reference for a sensitivity check.

WHAT THIS SCRIPT DOES AND DOES NOT DO. It writes a **cohort table only** — identifiers plus covariates,
one row per strict-normal recording, joined to the per-site EEG metadata for `BidsFolder` and duration.
**It reads no EEG signal and computes no candidate.** Building the reference values is a separate step
that consumes this table, and separating them is deliberate: the cohort definition is the thing that must
be frozen and inspected, and it should be reviewable without waiting hours for a signal pass.

    python analysis/heedb_normal_reference_cohort.py --out /tmp/eeg_probe/heedb_normal_reference.csv

NO PATIENT DATA IS COMMITTED. The output path defaults under `/tmp/eeg_probe/`, which is gitignored and
ephemeral by design — this is credentialed patient-derived data and it does not belong in the repository.
"""
from __future__ import annotations

import argparse
import collections
import csv
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.awsenv import sanitize as _aws_sanitize   # noqa: E402

AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
SITES = ("S0001", "S0002")
FINDINGS = "EEG/HEEDB_Metadata/{site}_EEG__reports_findings.csv"
EEGMETA = "EEG/eeg-metadata/{site}_eeg_metadata_2026_04_30.csv"
ICD = "EEG/HEEDB_Metadata/HEEDB_ICD10_for_Neurology.csv"

ABNORMAL_COLS = ("abnormal", "spikes", "seizure", "lpd", "gpd", "lrda", "grda", "bs",
                 "foc slowing", "gen slowing", "status", "uninterpretable", "low voltage",
                 "bipd", "eses", "cjd", "ppr", "breach", "diffuse Beta")
"""Every column whose presence disqualifies a read from the STRICT set.

Chosen to include anything that describes the RECORDING as departing from normal, and to exclude the
normal-variant and sleep-architecture columns (`spindles`, `vertex wave`, `k_complexes`, `posts`, `pdr`,
`awake`, `n1`, `n2`, `wicket`, `bets`) — a normal EEG containing sleep spindles is still a normal EEG, and
excluding those would select against anyone who fell asleep in the department. Syndrome columns that are
essentially never populated (`dravet`, `jeavons`, `sunflower`, `wham`, `angelman`, `fold`, `jae`, `jme`,
`bects`) are omitted for the same reason they are harmless: they carry no exclusions in practice."""


def _s3():
    _aws_sanitize(verbose=False)
    import boto3
    from botocore.config import Config
    try:
        sess = boto3.Session(profile_name="physionet")
        sess.client("sts").get_caller_identity()
    except Exception:                                                    # noqa: BLE001
        sess = boto3.Session()
    return sess.client("s3", region_name="us-east-1",
                       config=Config(s3={"payload_signing_enabled": False}))


def _get(cl, key):
    body = cl.get_object(Bucket=AP, Key=key)["Body"].read().decode("utf-8", "replace")
    return list(csv.DictReader(io.StringIO(body)))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="/tmp/eeg_probe/heedb_normal_reference.csv")
    ap.add_argument("--loose", action="store_true",
                    help="emit the LOOSE set (normal flagged, abnormality columns ignored) instead")
    a = ap.parse_args(argv)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    cl = _s3()

    print("loading the ICD-10 comorbidity table ...", flush=True)
    icd_rows = _get(cl, ICD)
    icd = {r["BDSPPatientID"]: r for r in icd_rows}
    icd_cols = [c for c in icd_rows[0].keys()
                if c not in ("BDSPPatientID", "SiteID", "SexDSC", "VisitCount", "AgeAtVisitAvg")]
    print(f"   {len(icd_rows)} patients, {len(icd_cols)} ICD chapters", flush=True)

    out_rows = []
    stats = collections.Counter()
    for site in SITES:
        print(f"{site}: findings ...", flush=True)
        find = _get(cl, FINDINGS.format(site=site))
        print(f"{site}: eeg-metadata ...", flush=True)
        meta = _get(cl, EEGMETA.format(site=site))
        by_key = {}
        for m in meta:
            k = (m.get("SiteID", ""), m.get("BDSPPatientID", ""), m.get("SessionID", ""))
            if k[1]:
                by_key[k] = m
        stats[f"{site}_recordings"] = len(find)

        for r in find:
            normal = (r.get("normal") or "").strip() != ""
            if not normal:
                continue
            stats[f"{site}_normal_flagged"] += 1
            any_abn = any((r.get(c) or "").strip() != "" for c in ABNORMAL_COLS)
            if any_abn and not a.loose:
                continue
            stats[f"{site}_selected"] += 1
            pid = (r.get("BDSPPatientID") or "").strip()
            m = by_key.get((site, pid, (r.get("SessionID") or "").strip()))
            if m is None:
                stats[f"{site}_no_metadata_join"] += 1
            ic = icd.get(pid)
            if ic is None:
                stats[f"{site}_no_icd_join"] += 1
            row = {
                "site": site,
                "patient_id": pid,
                "session_id": (r.get("SessionID") or "").strip(),
                "age_at_visit": (r.get("AgeAtVisit") or "").strip(),
                "sex": (r.get("SexDSC") or "").strip(),
                "service": (r.get("ServiceName(EEG)") or "").strip(),
                "start_time": (r.get("StartTime(EEG)") or "").strip(),
                "bids_folder": (m or {}).get("BidsFolder", ""),
                "eeg_folder": (m or {}).get("EEGFolder", ""),
                "duration_s": (m or {}).get("DurationInSeconds", ""),
                "n_icd_chapters": (sum(1 for c in icd_cols if (ic or {}).get(c, "").strip())
                                   if ic else ""),
            }
            for c in icd_cols:
                row["icd_" + c.replace(" ", "_").replace("/", "_")] = (
                    1 if (ic or {}).get(c, "").strip() else 0) if ic else ""
            out_rows.append(row)

    if not out_rows:
        print("\n   *** no rows selected — check the findings column names.")
        return 1
    fields = list(out_rows[0].keys())
    with open(a.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in out_rows:
            w.writerow(r)

    print("\n" + "=" * 90)
    print(f"{'LOOSE' if a.loose else 'STRICT'} normal-read reference cohort")
    print("=" * 90)
    for k in sorted(stats):
        print(f"   {k:28s} {stats[k]}")
    pats = {(r["site"], r["patient_id"]) for r in out_rows}
    print(f"   {'recordings written':28s} {len(out_rows)}")
    print(f"   {'unique patients':28s} {len(pats)}")
    withb = sum(1 for r in out_rows if r["bids_folder"])
    print(f"   {'with a BidsFolder':28s} {withb}  ({withb / len(out_rows):.1%})")
    print(f"\n   wrote {a.out}")
    print("   NOT committed: credentialed patient-derived data lives under /tmp/eeg_probe only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
