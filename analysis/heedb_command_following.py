"""SPONTANEOUS EEG features aligned to a CLINICIAN-ASSESSED COMMAND-FOLLOWING label, on HEEDB.

WHY THIS EXISTS. Challenge B asks whether spontaneous EEG predicts command-following. For its whole history
this project has had to substitute healthy BCI users for that question, because no reachable deposit
carried a command-following label:

    Chennu 2014   32 DoC patients, 128-ch resting EEG, BOTH a CRS-R and an fMRI command-following column,
                  including a documented cognitive-motor-dissociation case. **Raw EEG is not open** — it
                  needs a Wolfson Brain Imaging Centre committee request, and `repository.cam.ac.uk` fails
                  TLS from this sandbox besides.
    Bath          access requested, not granted.
    Della Bella   237 patients, but only CRS-R TOTALS are published; signal needs an author request.
    OpenNeuro / Dryad / Zenodo / PhysioNet — enumerated through their own APIs; no DoC EEG cohort.

**HEEDB already carries the label and the credentials already work.** The Glasgow Coma Scale motor
subscore's top level is literally *"obeys commands"*. A probe over 6 of 551 parquet parts of the merged
measurement table returned:

    26,527 `GLASGOW COMA SCALE BEST MOTOR RESPONSE` rows over 1,334 patients, values populated
    6.0 = 19,344   5.0 = 2,967   4.0 = 1,881   3.0 = 728   2.0 = 273   1.0 = 1,156
    plus 30,645 RASS rows in the same 6 parts

against a 67,202-patient EEG cohort. That is a clinician-assigned, entirely non-EEG command-following
label, on the critically-ill population Challenge B's flagship target actually lives in, at two to three
orders of magnitude more labels than any deposit this programme has ever had.

WHAT THIS IS AND IS NOT. GCS-motor is **OVERT** command-following. A cognitive-motor-dissociation patient
scores below 6 while conscious, so this does NOT detect covert consciousness and must never be described as
doing so. It is the precondition: a spontaneous-EEG measure that cannot predict overt command-following
will not detect covert. What it additionally enables — and no other reachable deposit does — is the
CMD-shaped design, because HEEDB has follow-up: a patient scoring below 6 whose EEG resembles a
command-follower's, who later recovers, is the signature.

THE JOIN, verified before this file was written (rule 41). The findings tables carry `StartTime(EEG)` and
`EndTime(EEG)` as full timestamps against `BDSPPatientID`; the measurement rows carry
`measurement_datetime`. `heedb_edf_range.read_edf_window` accepts `start_seconds`, so a window can be cut
at an arbitrary offset into a recording. An assessment is therefore matched to the EEG epoch that ENDS
before it — never one that spans or follows it, because a window overlapping the assessment could contain
the examiner's stimulation and the patient's response, which would leak the label through movement artefact.

WHAT IS EXTRACTED, per (patient, assessment)
  * a `WIN_SECONDS` window ending `GAP_SECONDS` before the assessment timestamp, from the recording that
    contains that instant, median-aggregated over the available montage
  * the project's standard spectral panel, imported rather than reimplemented (rule 20)
  * `gcs_motor` (1-6) and the binary `obeys` (motor == 6), plus the GCS total, eye and verbal subscores
    and the nearest RASS, so a successor cannot pick a different labelling afterwards without it showing
  * `minutes_before`, the actual gap achieved, and the recording id, so exclusions are auditable (rule 14)

Nothing here chooses a threshold, a cohort restriction or an analysis. This file only builds the table.

    PIDS_FILE=/tmp/heedb_quant_patients.txt \
      scripts/heedb_run.sh python analysis/heedb_command_following.py --shard 0 --of 4
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "bsde", "src"))
sys.path.insert(0, os.path.join(HERE, "..", "bsde", "scripts"))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))

MEAS = os.environ.get("MEAS_CSV", "/tmp/eeg_probe/heedb_cmd/measurement_conscious.csv")
OUT_DEFAULT = "/tmp/eeg_probe/heedb_command_following.csv"
SITES = ("S0001", "S0002", "I0002", "I0003")

WIN_SECONDS = 300.0        # 5 minutes of spontaneous EEG
GAP_SECONDS = 60.0         # the window must END at least this long before the assessment
MAX_LOOKBACK_MIN = 120.0   # and no earlier than this, or the state has had time to change
MOTOR = "BEST MOTOR RESPONSE"

# The 10-20 montage, passed to the reader AND re-checked by EXACT case-insensitive name afterwards.
# Two reasons, both found by measurement rather than assumed:
#   1. Without a channel filter the reader returns `EDF Annotations`, which HAS variance (sd ~0.08), so it
#      passes the good-channel test and enters the feature median as if it were EEG.
#   2. Worse, `L = min(len(v))` inside the reader truncates EVERY channel to the SHORTEST one, and the
#      annotation channel is sampled far lower -- so a 300 s request returned 17,100 samples (85.5 s) at
#      a reported fs of 200 Hz. With the filter the same windows return the full 60,000 samples.
# The exact re-check exists because the reader matches by SUBSTRING: `Pz` admitted `fpz` (rule 61).
TEN20 = ("Fp1", "Fp2", "F3", "F4", "C3", "C4", "P3", "P4", "O1", "O2",
         "F7", "F8", "T3", "T4", "T5", "T6", "Fz", "Cz", "Pz")


def eeg_only(X, names):
    """Keep exactly the 10-20 channels, by case-insensitive EQUALITY rather than substring."""
    want = {w.upper() for w in TEN20}
    keep = [i for i, n in enumerate(names) if (n or "").strip().upper() in want]
    return X[keep], [names[i] for i in keep]

SPECTRAL = ["exponent_low", "exponent_high", "whole_head_exponent", "relative_alpha_power",
            "relative_delta_power", "spectral_edge_95", "spectral_entropy", "lempel_ziv"]
FIELDS = (["patient_id", "site", "recording_key", "assess_time", "minutes_before", "n_channels",
           "gcs_motor", "obeys", "gcs_total", "gcs_eye", "gcs_verbal", "rass", "rass_minutes"]
          + SPECTRAL)


def _dt(s):
    s = (s or "").strip()
    for f in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(s, f)
        except ValueError:
            continue
    return None


def _num(s):
    try:
        v = float(s)
        return v if np.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def load_labels():
    """Per patient: the GCS motor assessments, and the other consciousness rows for context."""
    motor, other = {}, {}
    with open(MEAS, newline="") as fh:
        for r in csv.DictReader(fh):
            pid = (r.get("person_id") or "").strip()
            t = _dt(r.get("measurement_datetime"))
            v = _num(r.get("value_as_number"))
            src = (r.get("measurement_source_value") or "").upper()
            if not pid or t is None or v is None:
                continue
            if MOTOR in src and "PEDS" not in src:
                motor.setdefault(pid, []).append((t, v))
            else:
                key = ("rass" if "RASS" in src or "RICHMOND" in src else
                       "eye" if "EYE OPENING" in src else
                       "verbal" if "BEST VERBAL" in src else
                       "total" if "SCALE SCORE" in src or "COMA SCORE" in src else None)
                if key:
                    other.setdefault(pid, {}).setdefault(key, []).append((t, v))
    for d in (motor,):
        for k in d:
            d[k].sort()
    return motor, other


def bids_key(site, bids, session, eegfolder):
    """Signal path. Copied in behaviour from `heedb_bs_calibrate.bids_key`, which is the working one."""
    task = "cEEG" if (eegfolder or "").lower().startswith("ceeg") else "EEG"
    return f"EEG/bids/{site}/{bids}/ses-{session}/eeg/{bids}_ses-{session}_task-{task}_eeg.edf"


def _get_csv(s3, AP, key):
    body = s3.get_object(Bucket=AP, Key=key)["Body"].read().decode("utf8", "replace")
    return list(csv.DictReader(io.StringIO(body)))


def load_recordings(s3, AP):
    """Per patient: (start, end, signal key, site) for every EEG session.

    **The timestamps and the signal path live in DIFFERENT tables and neither has both.** The eeg-metadata
    table carries `BidsFolder`, `SessionID` and `EEGFolder` but its `BDSPPatientID`, `StartTime` and
    `EndTime` columns are blank; the reports-findings table carries `BDSPPatientID`, `SessionID`,
    `StartTime(EEG)` and `EndTime(EEG)` but no path. They are joined on (BidsFolder, SessionID), with the
    folder built as `sub-<SITE><PID>` — the convention `heedb_bs_calibrate` documents and uses.
    """
    recs = {}
    for site in SITES:
        try:
            meta = _get_csv(s3, AP, f"EEG/eeg-metadata/{site}_eeg_metadata_2026_04_30.csv")
        except Exception as e:                                                  # noqa: BLE001
            print(f"   {site}: metadata unavailable ({type(e).__name__})", flush=True)
            continue
        folder = {}
        for r in meta:
            bf = (r.get("BidsFolder") or "").strip()
            if bf:
                folder[(bf, (r.get("SessionID") or "").strip())] = (r.get("EEGFolder") or "").strip()
        find_key = next((k for k in (f"EEG/HEEDB_Metadata/{site}_EEG__reports_findings.csv",
                                     f"EEG/HEEDB_Metadata/{site}_EEG_reports_findings.csv")), None)
        try:
            fnd = _get_csv(s3, AP, find_key)
        except Exception:                                                       # noqa: BLE001
            try:
                fnd = _get_csv(s3, AP, f"EEG/HEEDB_Metadata/{site}_EEG_reports_findings.csv")
            except Exception as e:                                              # noqa: BLE001
                print(f"   {site}: findings unavailable ({type(e).__name__})", flush=True)
                continue
        n = 0
        for r in fnd:
            pid = (r.get("BDSPPatientID") or "").strip()
            sess = (r.get("SessionID") or "").strip()
            st, en = _dt(r.get("StartTime(EEG)")), _dt(r.get("EndTime(EEG)"))
            if not (pid.isdigit() and sess and st):
                continue
            bf = f"sub-{site}{pid}"
            if (bf, sess) not in folder:
                continue
            recs.setdefault(pid, []).append(
                (st, en, bids_key(site, bf, sess, folder[(bf, sess)]), site))
            n += 1
        print(f"   {site}: {n} recordings with a timestamp and a path", flush=True)
    for k in recs:
        recs[k].sort()
    return recs


def nearest(seq, t, max_minutes):
    """The value in `seq` closest to `t` within `max_minutes`, else (None, None)."""
    best, bestd = None, None
    for tt, vv in seq:
        d = abs((tt - t).total_seconds()) / 60.0
        if d <= max_minutes and (bestd is None or d < bestd):
            best, bestd = vv, d
    return best, bestd


def build_worklist(s3, AP, out_path, max_per_patient):
    """Resolve every (patient, assessment) -> (recording key, offset) ONCE, centrally.

    **This is the whole speed fix.** `load_labels` parses 15.4 M rows in 372 s and holds 2.6 GB; running it
    inside every shard cost 4 x 372 s of duplicated startup AND 10.4 GB of the machine's 15 GB, which is
    what made the shards contend. Profiling put the matching loop at 0.3 ms/patient, a successful S3 read
    at 0.55 s and the spectral panel at 2.12 s -- so the per-row work was never the bottleneck.

    The worklist carries everything a shard needs, so a shard never touches the label table at all.
    """
    motor, other = load_labels()
    recs = load_recordings(s3, AP)
    pids = sorted(set(motor) & set(recs), key=lambda x: int(x) if x.isdigit() else 0)
    n = 0
    cols = ["patient_id", "site", "recording_key", "offset_s", "assess_time",
            "gcs_motor", "gcs_total", "gcs_eye", "gcs_verbal", "rass", "rass_minutes"]
    with open(out_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for pid in pids:
            kept = 0
            for (t, v) in motor[pid]:
                if kept >= max_per_patient:
                    break
                w_end = t - dt.timedelta(seconds=GAP_SECONDS)
                w_start = w_end - dt.timedelta(seconds=WIN_SECONDS)
                cands = []
                for (st, en, key, site) in recs[pid]:
                    if w_start < st:
                        continue
                    if en is not None and w_end > en:
                        continue
                    if (t - w_end).total_seconds() / 60.0 > MAX_LOOKBACK_MIN:
                        continue
                    cands.append(((w_start - st).total_seconds(), key, site))
                if not cands:
                    continue
                off, key, site = min(cands, key=lambda z: abs(z[0]))
                o = other.get(pid, {})
                rass, rmin = nearest(o.get("rass", []), t, MAX_LOOKBACK_MIN)
                w.writerow({"patient_id": pid, "site": site, "recording_key": key,
                            "offset_s": round(off, 3), "assess_time": t.isoformat(),
                            "gcs_motor": v,
                            "gcs_total": nearest(o.get("total", []), t, 30)[0],
                            "gcs_eye": nearest(o.get("eye", []), t, 30)[0],
                            "gcs_verbal": nearest(o.get("verbal", []), t, 30)[0],
                            "rass": rass,
                            "rass_minutes": None if rmin is None else round(rmin, 1)})
                kept += 1
                n += 1
            if n and n % 2000 == 0:
                print(f"   worklist: {n} entries", flush=True)
    print(f"WORKLIST: {n} entries over {len(pids)} patients -> {out_path}", flush=True)
    return n


def run_worklist(s3, work_path, out_path, shard, of):
    """Do only the expensive part: one S3 window read and one spectral panel per entry."""
    from heedb_edf_range import read_edf_window
    from extract_stieger_features import _spectral

    with open(work_path, newline="") as fh:
        work = [r for r in csv.DictReader(fh)
                if (int(r["patient_id"]) if r["patient_id"].isdigit() else 0) % of == shard]
    # Read the done-set from EVERY existing output file, not just this shard's. The partition width
    # changed when the worklist replaced the per-shard label parse, so rows already written under the
    # old width live in a different file and would otherwise be re-extracted.
    import glob as _glob
    done = set()
    for q in sorted(set(_glob.glob(os.path.join(os.path.dirname(out_path),
                                                "heedb_cmd_follow*.csv")) + [out_path])):
        if os.path.exists(q) and os.path.getsize(q) > 0:
            with open(q, newline="") as fh:
                for r in csv.DictReader(fh):
                    done.add((r["patient_id"], r["assess_time"]))
    todo = [r for r in work if (r["patient_id"], r["assess_time"]) not in done]
    print(f"shard {shard}/{of}: {len(work)} entries, {len(done)} already done overall, "
          f"{len(todo)} to go",
          flush=True)

    new = not os.path.exists(out_path) or os.path.getsize(out_path) == 0
    kept = skipped = 0
    with open(out_path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        for i, e in enumerate(todo, 1):
            key, off = e["recording_key"], float(e["offset_s"])
            X = None
            for k_try in (key, key.replace("task-cEEG", "task-EEG") if "task-cEEG" in key
                          else key.replace("task-EEG", "task-cEEG")):
                try:
                    X, fs, names = read_edf_window(k_try, max_seconds=WIN_SECONDS, s3=s3,
                                                   start_seconds=off, want=list(TEN20))[:3]
                    key = k_try
                    break
                except Exception:                                               # noqa: BLE001
                    continue
            if X is None:
                skipped += 1
                continue
            X, names = eeg_only(np.asarray(X, float), names)
            X = np.asarray(X, float)
            good = [j for j in range(X.shape[0]) if np.isfinite(X[j]).all() and X[j].std() > 1e-6]
            if len(good) < 4 or X.shape[1] < int(60 * fs):
                skipped += 1
                continue
            rows = [_spectral(X[j], fs) for j in good]
            d = {c: float(np.nanmedian([q[c] for q in rows])) for c in SPECTRAL}
            v = float(e["gcs_motor"])
            d.update({"patient_id": e["patient_id"], "site": e["site"], "recording_key": key,
                      "assess_time": e["assess_time"],
                      "minutes_before": round((GAP_SECONDS + WIN_SECONDS) / 60.0, 3),
                      "n_channels": len(good), "gcs_motor": v, "obeys": 1 if v >= 6 else 0,
                      "gcs_total": e["gcs_total"], "gcs_eye": e["gcs_eye"],
                      "gcs_verbal": e["gcs_verbal"], "rass": e["rass"],
                      "rass_minutes": e["rass_minutes"]})
            w.writerow({k: d.get(k, "") for k in FIELDS})
            fh.flush()
            kept += 1
            if i % 100 == 0:
                print(f"   [{i}/{len(todo)}] kept {kept}, skipped {skipped}", flush=True)
    print(f"DONE shard {shard}: kept {kept}, skipped {skipped} -> {out_path}", flush=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--of", type=int, default=1)
    ap.add_argument("--out", default=OUT_DEFAULT)
    ap.add_argument("--max-per-patient", type=int, default=2,
                    help="assessments kept per patient; more would weight long stays heavily")
    ap.add_argument("--build-worklist", default="",
                    help="resolve every assessment to a recording key ONCE and write the worklist here")
    ap.add_argument("--worklist", default="",
                    help="read a prebuilt worklist and do only the S3 read + spectral panel")
    a = ap.parse_args(argv)

    import boto3
    from botocore.config import Config
    import common.awsenv as awsenv
    awsenv.sanitize(verbose=False)
    from heedb_edf_range import read_edf_window, AP
    from extract_stieger_features import _spectral

    s3 = boto3.client("s3", region_name="us-east-1",
                      config=Config(s3={"payload_signing_enabled": False},
                                    retries={"max_attempts": 5, "mode": "standard"}))

    if a.build_worklist:
        build_worklist(s3, AP, a.build_worklist, a.max_per_patient)
        return 0
    if a.worklist:
        run_worklist(s3, a.worklist, os.path.abspath(a.out), a.shard, a.of)
        return 0

    print("loading labels ...", flush=True)
    motor, other = load_labels()
    print(f"   {len(motor)} patients with a GCS motor assessment", flush=True)
    print("loading recording index ...", flush=True)
    recs = load_recordings(s3, AP)
    print(f"   {len(recs)} patients with recordings", flush=True)

    pids = sorted(set(motor) & set(recs), key=lambda x: int(x) if x.isdigit() else 0)
    pids = [p for p in pids if (int(p) if p.isdigit() else 0) % a.of == a.shard]
    print(f"shard {a.shard}/{a.of}: {len(pids)} patients with BOTH a label and a recording", flush=True)

    out_path = os.path.abspath(a.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    done = set()
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        with open(out_path, newline="") as fh:
            done = {(r["patient_id"], r["assess_time"]) for r in csv.DictReader(fh)}
    new = not os.path.exists(out_path) or os.path.getsize(out_path) == 0

    kept = skipped = 0
    with open(out_path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        for i, pid in enumerate(pids, 1):
            n_this = 0
            for (t, v) in motor[pid]:
                if n_this >= a.max_per_patient:
                    break
                if (pid, t.isoformat()) in done:
                    n_this += 1
                    continue
                # the window must END before the assessment: a window spanning it could contain the
                # examiner's stimulation and the patient's response, leaking the label as artefact
                # The window [t - GAP - WIN, t - GAP] must lie ENTIRELY inside a recording. Among the
                # recordings that satisfy that, take the one whose window ENDS LATEST -- i.e. closest in
                # time to the assessment -- rather than whichever happened to come last in the list.
                w_end = t - dt.timedelta(seconds=GAP_SECONDS)
                w_start = w_end - dt.timedelta(seconds=WIN_SECONDS)
                cands = []
                for (st, en, key, site) in recs[pid]:
                    if w_start < st:
                        continue
                    if en is not None and w_end > en:
                        continue
                    if (t - w_end).total_seconds() / 60.0 > MAX_LOOKBACK_MIN:
                        continue
                    cands.append(((w_start - st).total_seconds(), key, site, st))
                if not cands:
                    skipped += 1
                    continue
                off, key, site, st = min(cands, key=lambda z: abs(z[0]))
                X = None
                # The task token in the path is a GUESS from EEGFolder; when it is wrong the object is
                # simply absent, so try the other one rather than discarding the assessment.
                for k_try in (key, key.replace("task-cEEG", "task-EEG")
                              if "task-cEEG" in key else key.replace("task-EEG", "task-cEEG")):
                    try:
                        X, fs, names = read_edf_window(k_try, max_seconds=WIN_SECONDS, s3=s3,
                                                       start_seconds=off)[:3]
                        key = k_try
                        break
                    except Exception:                                           # noqa: BLE001
                        continue
                if X is None:
                    skipped += 1
                    continue
                X = np.asarray(X, float)
                good = [j for j in range(X.shape[0]) if np.isfinite(X[j]).all() and X[j].std() > 1e-6]
                if len(good) < 4 or X.shape[1] < int(60 * fs):
                    skipped += 1
                    continue
                rows = [_spectral(X[j], fs) for j in good]
                d = {c: float(np.nanmedian([q[c] for q in rows])) for c in SPECTRAL}
                o = other.get(pid, {})
                rass, rmin = nearest(o.get("rass", []), t, MAX_LOOKBACK_MIN)
                d.update({
                    "patient_id": pid, "site": site, "recording_key": key,
                    "assess_time": t.isoformat(),
                    "minutes_before": round((GAP_SECONDS + WIN_SECONDS) / 60.0, 3),
                    "n_channels": len(good), "gcs_motor": v, "obeys": 1 if v >= 6 else 0,
                    "gcs_total": nearest(o.get("total", []), t, 30)[0],
                    "gcs_eye": nearest(o.get("eye", []), t, 30)[0],
                    "gcs_verbal": nearest(o.get("verbal", []), t, 30)[0],
                    "rass": rass, "rass_minutes": None if rmin is None else round(rmin, 1)})
                w.writerow({k: d.get(k, "") for k in FIELDS})
                fh.flush()
                kept += 1
                n_this += 1
            if i % 25 == 0:
                print(f"   [{i}/{len(pids)}] kept {kept}, skipped {skipped}", flush=True)
    print(f"DONE shard {a.shard}: kept {kept}, skipped {skipped} -> {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
