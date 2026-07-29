#!/usr/bin/env python3
"""Split the lead's measure into its parts: alpha vs beta, fast vs slow, and its within-patient dispersion.

WHY THIS EXTRACTION EXISTS. The lead is that intra-burst `alpha_beta` = P[8-30] / P[1-30] ranks 30-day death
in OPPOSITE directions by aetiology. Three of the seven surviving mechanism candidates (2026-07-29 brainstorm)
make different predictions about WHICH PART of that ratio carries the reversal, and none can be tested from
the cached median alone:

    F1  ALPHA COMA          the reversal is carried by the ALPHA sub-band (8-13 Hz). Monotonous non-reactive
                            alpha after anoxia is a named malignant entity; alpha elsewhere means arousal.
                            -> alpha_frac interacts with aetiology; beta_frac does not (or does so weakly).
    F2  THE SLOW DENOMINATOR  `alpha_beta` is a RATIO, so a high value also means LITTLE 1-8 Hz content. The
                            "reversal in fast content" may really be a reversal in SLOW content seen through
                            the denominator. -> slow_frac carries it, and absolute fast power does not.
    F3  MONOTONY            alpha coma's defining feature is non-reactivity, not alpha per se. Fast content
                            that is INVARIANT across bursts is malignant; fluctuating fast content is benign.
                            -> the within-patient DISPERSION of alpha_beta carries it, not its median.

One S3 pass answers all three, so they are extracted together rather than in three passes.

WHAT IS HELD FIXED. The burst segmentation is imported unchanged from `heedb_burst_morphology` --
`suppression_mask`, `runs_of` and the FRAME_S / MIN_RUN_S / MIN_BURST_S constants -- so these features are
measured on EXACTLY the bursts the validated extraction found. Nothing about burst detection is re-implemented
here, because a re-implementation would confound "different band" with "different bursts".

THE BUILT-IN CORRECTNESS CHECK, and it is the reason `alpha_beta` is recomputed rather than joined. This
script re-derives the SAME quantity the cached table holds. If the new `alpha_beta` does not reproduce the
cached one per patient, the extraction has drifted and every sub-band number is suspect. That check is run by
`heedb_subband_analysis.py` before any sub-band result is interpreted (catalogue rules 20 and 23: when two
scripts compute the same quantity, diff them; validate against an independent implementation).

DEFINITIONS, all on the same 1-30 Hz denominator so the fractions are comparable and sum to 1:
    alpha_frac = P[8-13]  / P[1-30]
    beta_frac  = P[13-30] / P[1-30]
    slow_frac  = P[1-8]   / P[1-30]          (= 1 - alpha_beta, carried explicitly for readability)
    alpha_beta = P[8-30]  / P[1-30]          (reproduction of the cached measure)
    ab_iqr     = IQR of per-burst alpha_beta within a window  -> F3's monotony handle
    log_fast_pw / log_slow_pw = log10 ABSOLUTE band power, which the ratios deliberately discard. F2 needs
                 absolute power, because a ratio cannot distinguish "more fast" from "less slow".

Sharded and resumable, one output file per shard, same contract as the parent script: an interrupted run
loses nothing and a partial run is still analysable.
"""
import argparse, csv, io, os, sys, time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.awsenv import sanitize as _aws_sanitize; _aws_sanitize()

from heedb_burst_morphology import (suppression_mask, runs_of, THRESH_UV, N_WINDOWS,
                                    WIN_SECONDS, LEAD_IN_FRAC, MIN_BURST_S)

OUT = os.environ.get("SUBBAND_OUT", "/tmp/eeg_probe/heedb_burst_subband.csv")
COLS = ["site", "patient", "bids", "session", "n_bursts", "alpha_beta", "alpha_frac",
        "beta_frac", "slow_frac", "ab_iqr", "log_fast_pw", "log_slow_pw"]


def subband(x, fs, thresh):
    """Per-window sub-band features on the SAME bursts heedb_burst_morphology would find."""
    supp, _ = suppression_mask(x, fs, thresh)
    if supp is None:
        return None
    fr = max(1, int(0.1 * fs))
    segs = []
    for a, b in runs_of(supp, False):                 # bursts = the non-suppressed runs
        if (b - a) * fr / fs >= MIN_BURST_S:
            segs.append(x[a * fr:b * fr])
    if not segs:
        return None
    ab, al, be, sl, fastp, slowp = [], [], [], [], [], []
    for s in segs:
        if len(s) < int(0.5 * fs):
            continue
        f = np.fft.rfftfreq(len(s), 1.0 / fs)
        P = np.abs(np.fft.rfft(s * np.hanning(len(s)))) ** 2
        m_tot = (f >= 1) & (f <= 30)
        tot = P[m_tot].sum()
        if tot <= 0:
            continue
        p_alpha = P[(f >= 8) & (f < 13)].sum()
        p_beta = P[(f >= 13) & (f <= 30)].sum()
        p_slow = P[(f >= 1) & (f < 8)].sum()
        ab.append(float((p_alpha + p_beta) / tot))
        al.append(float(p_alpha / tot))
        be.append(float(p_beta / tot))
        sl.append(float(p_slow / tot))
        fastp.append(float(p_alpha + p_beta))
        slowp.append(float(p_slow))
    if not ab:
        return None
    q75, q25 = np.percentile(ab, [75, 25])
    return dict(n_bursts=len(segs),
                alpha_beta=float(np.median(ab)),
                alpha_frac=float(np.median(al)),
                beta_frac=float(np.median(be)),
                slow_frac=float(np.median(sl)),
                ab_iqr=float(q75 - q25),
                log_fast_pw=float(np.log10(max(np.median(fastp), 1e-12))),
                log_slow_pw=float(np.log10(max(np.median(slowp), 1e-12))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--nshards", type=int, default=1)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    if not (0 <= args.shard < args.nshards):
        print("bad shard"); return 2

    import boto3, glob as _glob
    from botocore.config import Config
    from heedb_edf_range import read_edf_window, AP
    from heedb_bs_calibrate import prep, bids_key

    s3 = boto3.client("s3", region_name="us-east-1",
                      config=Config(s3={"payload_signing_enabled": False},
                                    retries={"max_attempts": 4, "mode": "standard"}))

    pfile = os.environ.get("PATIENTS_FILE", "/tmp/heedb_morph_patients.txt")
    want = {int(x) for x in open(pfile).read().split() if x.strip().isdigit()}
    assert want, f"{pfile} produced no patient ids"
    print(f"patients targeted: {len(want)} (from {pfile})", flush=True)

    recs = []
    for site in ("S0001", "S0002"):
        try:
            txt = s3.get_object(Bucket=AP,
                                Key=f"EEG/eeg-metadata/{site}_eeg_metadata_2026_04_30.csv"
                                )["Body"].read().decode("utf-8", "replace")
        except Exception as e:
            print(f"  {site}: {type(e).__name__}"); continue
        for r in csv.DictReader(io.StringIO(txt)):
            pid = (r.get("BDSPPatientID") or "").strip()
            bids = (r.get("BidsFolder") or "").strip()
            if not pid.isdigit() or not bids or int(pid) not in want:
                continue
            recs.append((site, pid, bids, (r.get("EEGFolder") or "").strip(),
                         (r.get("SessionID") or "").strip()))
    # Earliest session per patient -- identical rule to the parent extraction, so the sub-band values
    # describe the SAME recording as the cached alpha_beta they are checked against.
    best = {}
    for r in recs:
        try:
            sess = int(r[4])
        except Exception:
            continue
        if r[1] not in best or sess < best[r[1]][0]:
            best[r[1]] = (sess, r)
    recs = [v[1] for v in best.values()]
    print(f"earliest session per patient: {len(recs)}", flush=True)

    out_path = OUT if args.nshards == 1 else OUT[:-4] + f".s{args.shard}.csv"
    done = set()
    for p in sorted(set([OUT] + _glob.glob(OUT[:-4] + ".s*.csv"))):
        if os.path.exists(p):
            for r in csv.DictReader(open(p)):
                done.add((r["site"], r["bids"], r["session"]))
    todo = [x for x in recs if (x[0], x[2], x[4]) not in done]
    if args.nshards > 1:
        todo = todo[args.shard::args.nshards]
    if args.limit:
        todo = todo[:args.limit]
    print(f"already done {len(done)}, to do {len(todo)} "
          f"(shard {args.shard}/{args.nshards} -> {out_path})", flush=True)

    newf = not os.path.exists(out_path)
    fh = open(out_path, "a", newline=""); w = csv.writer(fh)
    if newf:
        w.writerow(COLS); fh.flush()

    t0 = time.time(); ok = 0
    for i, (site, pid, bids, eegfolder, sess) in enumerate(todo, 1):
        try:
            key = bids_key(site, bids, sess, eegfolder)
            acc = []
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
                per = [subband(c, fs, THRESH_UV) for c in chans]
                per = [d for d in per if d]
                if per:
                    acc.append({k: float(np.nanmedian([d[k] for d in per])) for k in per[0]})
            if acc:
                agg = {k: float(np.nanmedian([d[k] for d in acc])) for k in acc[0]}
                w.writerow([site, pid, bids, sess, int(agg["n_bursts"])]
                           + [round(agg[k], 6) for k in
                              ("alpha_beta", "alpha_frac", "beta_frac", "slow_frac",
                               "ab_iqr", "log_fast_pw", "log_slow_pw")])
                fh.flush(); ok += 1
        except Exception:
            pass
        if i % 25 == 0:
            el = (time.time() - t0) / 60
            print(f"  [{i}/{len(todo)}] ok={ok}  {el:.1f} min  "
                  f"{i/max(el,1e-9):.1f} rec/min", flush=True)
    fh.close()
    print(f"DONE shard {args.shard}: {ok}/{len(todo)} recordings -> {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
