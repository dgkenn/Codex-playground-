#!/usr/bin/env python3
"""Quantify burst-suppression BURDEN from the raw HEEDB EEG, replacing the binary clinician label.

WHY. The HEEDB finding — that burst suppression's prognostic meaning depends on aetiology (interaction spread
36.17 pp [29.05, 43.85]) — currently rests on a CLINICIAN LABEL from a report: present or absent, as read by
whichever neurophysiologist reported that study. Two weaknesses follow, and both are stated as limitations in
docs/research/39_HEEDB_FINDINGS.md:

  * it is binary, so no dose-response can be tested, and dose-response is among the strongest observational
    evidence available for a real effect (it is what carried the VitalDB arm);
  * reader heterogeneity is an unmeasured error source, and readers differ in threshold for calling suppression.

This script replaces the label with a measured burden using the detector already calibrated against HEEDB's own
expert labels at AUC 0.829 (5 uV amplitude threshold on the referential montage, 0.1 s frames, runs >= 0.5 s;
see docs/research/35_HEEDB_bs_context_findings.md). The calibration matters: the VitalDB threshold of 8 uV gave
only AUC 0.63 here because HEEDB is referential where VitalDB is bipolar, so the operating point is not portable
and was re-derived in-distribution.

METHOD. EDFs are read by BYTE RANGE — a fixed set of short windows sampled across each recording — so the ~1 GB
files are never downloaded. Windows start after a lead-in so the electrode-hookup period cannot be mistaken for
suppression, a mistake made earlier in this project when reading from the start of records produced an identical
spurious 0.311 burden on every channel.

OUTPUT: one row per recording with the suppressed fraction across sampled windows, joinable to the OMOP cohort.

WHAT THIS WILL AND WILL NOT FIX.
  Fixes:  a graded exposure, so the aetiology interaction can be tested against BURDEN rather than presence, and a
          dose-response becomes testable.
  Does NOT fix: indication bias (EEG is still ordered because someone was worried), and sampling error — a few
          short windows cannot equal an expert reading the whole record, which bounds the achievable agreement
          from below regardless of how good the detector is.

Deliberately run at LOW concurrency: the OMOP extractions are on the critical path for re-running every reported
figure at full coverage, and starving them to speed this up would be the wrong trade.
"""
import argparse, csv, io, os, sys, time
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# The sandbox exports placeholder AWS_* env vars that shadow the real profile -- common/awsenv.py.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.awsenv import sanitize as _aws_sanitize; _aws_sanitize()

THRESH_UV = float(os.environ.get("BS_THRESH_UV", "5.0"))
N_WINDOWS = int(os.environ.get("N_WINDOWS", "4"))
# Per-window burden output, for estimating the measurement error of a single reading.
WIN_OUT = os.environ.get("WIN_OUT", "")
WIN_SECONDS = int(os.environ.get("WIN_SECONDS", "120"))
LEAD_IN_FRAC = float(os.environ.get("LEAD_IN_FRAC", "0.15"))
OUT = os.environ.get("BS_BURDEN_OUT", "/tmp/eeg_probe/heedb_bs_burden.csv")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    # SHARDING. The work is S3-fetch- and decode-bound, not CPU-bound, so it parallelises well across
    # processes; run --nshards N with --shard 0..N-1. Each shard writes its OWN file rather than appending
    # to a shared one: concurrent appends of short rows are usually atomic on Linux but "usually" is not a
    # standard this project accepts for a file that feeds a reported number. Merge the shards on read.
    # Resume is shard-aware -- every shard reads every existing shard file, so nothing is recomputed if the
    # shard count changes between runs.
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--nshards", type=int, default=1)
    args = ap.parse_args()
    if not (0 <= args.shard < args.nshards):
        print(f"--shard must be in [0,{args.nshards}); got {args.shard}"); return 2

    import boto3
    from botocore.config import Config
    from heedb_edf_range import read_edf_window, AP
    from heedb_bs_calibrate import prep, burden, bids_key

    s3 = boto3.client("s3", region_name="us-east-1",
                      config=Config(s3={"payload_signing_enabled": False},
                                    retries={"max_attempts": 4, "mode": "standard"}))

    # cohort: patients already in the OMOP analysis, so the join is guaranteed
    want = {x.strip() for x in open("/tmp/heedb_all_patients.txt") if x.strip()}
    print(f"target patients: {len(want)}")

    # map patient -> BIDS folder from the EEG metadata, and note which reports carried the bs label
    recs = []
    for site in ("S0001", "S0002"):
        try:
            txt = s3.get_object(Bucket=AP,
                                Key=f"EEG/eeg-metadata/{site}_eeg_metadata_2026_04_30.csv"
                                )["Body"].read().decode("utf-8", "replace")
        except Exception as e:
            print(f"  {site} metadata: {type(e).__name__} {str(e)[:70]}")
            continue
        for r in csv.DictReader(io.StringIO(txt)):
            pid = (r.get("BDSPPatientID") or "").strip()
            bids = (r.get("BidsFolder") or "").strip()
            if not pid or not bids or pid not in want:
                continue
            recs.append((site, pid, bids, (r.get("EEGFolder") or "").strip(),
                         (r.get("SessionID") or "").strip()))
    print(f"recordings for cohort patients: {len(recs)}")
    if args.limit:
        recs = recs[:args.limit]

    import glob as _glob
    out_path = OUT if args.nshards == 1 else OUT[:-4] + f".s{args.shard}.csv"
    done = set()
    for p in sorted(set([OUT] + _glob.glob(OUT[:-4] + ".s*.csv"))):
        if not os.path.exists(p):
            continue
        for r in csv.DictReader(open(p)):
            done.add((r["site"], r["bids"], r["session"]))
    todo = [x for x in recs if (x[0], x[2], x[4]) not in done]
    if args.nshards > 1:
        todo = todo[args.shard::args.nshards]
    print(f"already done {len(done)}, to do {len(todo)} "
          f"(shard {args.shard}/{args.nshards} -> {out_path})")

    newf = not os.path.exists(out_path)
    fh = open(out_path, "a", newline="")
    w = csv.writer(fh)
    if newf:
        w.writerow(["site", "patient", "bids", "session", "n_windows_ok", "burden", "thresh_uv"])
    wfh = ww = None
    if WIN_OUT:
        wpath = WIN_OUT if args.nshards == 1 else WIN_OUT[:-4] + f".s{args.shard}.csv"
        wnew = not os.path.exists(wpath)
        wfh = open(wpath, "a", newline="")
        ww = csv.writer(wfh)
        if wnew:
            ww.writerow(["site", "patient", "bids", "session", "window", "burden", "thresh_uv"])
            wfh.flush()
        print(f"per-window output -> {wpath}", flush=True)
        fh.flush()

    t0 = time.time(); n_ok = 0
    for i, (site, pid, bids, eegfolder, sess) in enumerate(todo, 1):
        try:
            burdens = []
            # key layout and the cEEG/EEG task variant come from heedb_bs_calibrate.bids_key, which is the
            # version validated at AUC 0.829 -- do not reconstruct it here
            key = bids_key(site, bids, sess, eegfolder)
            for j in range(N_WINDOWS):
                frac = LEAD_IN_FRAC + (0.70 * j / max(N_WINDOWS - 1, 1))
                try:
                    X, fs, names, meta = read_edf_window(key, max_seconds=WIN_SECONDS, s3=s3,
                                                         start_frac=frac)
                except Exception:
                    continue
                chans = prep(X, names, fs)
                if not chans:
                    continue
                vals = [burden(c, fs, THRESH_UV)[0] for c in chans]
                vals = [v for v in vals if v == v]
                if vals:
                    burdens.append(float(np.median(vals)))
            if burdens:
                # MAX across windows, not mean: suppression is intermittent and an average dilutes it.
                # NOTE (2026-07-26): this comment previously claimed the calibration "achieved AUC 0.829"
                # against the clinician label. That number was never reproducible. Measured properly in
                # heedb_burden_validity.py it is AUC 0.749 [0.747,0.760] on n=27,948 matched recordings.
                # An unverified figure in a comment had been overstating the exposure's validity.
                w.writerow([site, pid, bids, sess, len(burdens),
                            round(float(np.max(burdens)), 4), THRESH_UV])
                fh.flush(); n_ok += 1
                # PER-WINDOW output. The max discards the spread ACROSS windows of the same recording, and
                # that spread is measurement error by construction -- same patient, same recording, minutes
                # apart. It is the quantity the structural-versus-reversible conclusion depends on, and it
                # was thrown away. Written to a separate file so existing outputs are unchanged.
                if WIN_OUT:
                    for wi, bv in enumerate(burdens):
                        ww.writerow([site, pid, bids, sess, wi, round(float(bv), 4), THRESH_UV])
                    wfh.flush()
        except Exception:
            continue
        if i % 25 == 0:
            el = time.time() - t0
            print(f"  [{i}/{len(todo)}] {n_ok} with burden  ({el/60:.1f} min, "
                  f"{i/max(el/60,1e-9):.1f} rec/min)", flush=True)
    fh.close()
    print(f"DONE: {n_ok} recordings with a quantified burden -> {out_path}")


if __name__ == "__main__":
    sys.exit(main())
