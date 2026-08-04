#!/usr/bin/env python3
"""Is the BACKGROUND the better measurement? Whole-record slow activity vs intra-burst spectral content.

WHY THIS EXISTS. The convergent-validity test (R358–R360) found that the clinician's "generalized slowing" flag
and our intra-burst 8–30 Hz measure agree — the agreement survives within every burden tertile, so it is not a
suppression proxy — but that the **flag still carries −0.752 [−1.075, −0.434] after adjusting for burden AND our
measure**. The two share a factor without being the same construct.

The obvious reading: slow activity lives largely in the record **between and around** bursts, and our measure
looks only **inside** them. If so, our morphology channel is a weak proxy for a better-measured quantity — and
that would explain N10, the finding that morphology's predictive increment is marginal in one cohort and null
in the other.

REGISTERED PREDICTIONS, fixed before running.
  B1  Whole-record relative slow power (delta+theta as a fraction of 1–30 Hz) is HIGHER in good outcome.
      Direction taken from the clinician flag: slowing present marks survival (74.9 % vs 29.7 %).
  B2  It carries outcome information after adjusting for suppression burden.
  B3  THE ONE THAT MATTERS. It carries outcome information after adjusting for burden AND for intra-burst
      8–30 Hz content. If it does, the background is the better measurement and intra-burst content is the
      weak proxy — which is what R360 implies and what would explain N10.
      FALSIFIED IF the whole-record measure adds nothing beyond the intra-burst one.

WHY RELATIVE, NOT ABSOLUTE. A suppressed record has low power at every frequency, so absolute band power is
largely a restatement of burden. Relative power (a band as a fraction of total 1–30 Hz) is scale-free and
therefore asks about the SHAPE of the spectrum rather than its size — which is the question.

THE LIMIT THAT TRAVELS WITH THIS. Unlike burst morphology, these measures are defined for EVERY recording,
including near-totally suppressed ones. That fixes the 13.2 % outcome-related exclusion (L1) which conditioned
every morphology result on having at least four bursts. If the background measure works, it works on the
patients morphology could not see — which are the sickest ones.
"""
import csv, io, os, re, sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np

AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-restricted-access-point"
ROOT = "ICARE_train/training/"
OUT = os.environ.get("ICARE_BG_OUT", "/tmp/eeg_probe/icare_background.csv")
HOUR = float(os.environ.get("ICARE_HOUR", "24"))
THRESH = float(os.environ.get("ICARE_THRESH", "8.0"))
FRAME_S, MIN_RUN_S = 0.1, 0.5
PAIRS = [("FP1", "F3"), ("F3", "C3"), ("C3", "P3"), ("P3", "O1"),
         ("FP2", "F4"), ("F4", "C4"), ("C4", "P4"), ("P4", "O2")]
BANDS = {"delta": (1, 4), "theta": (4, 8), "alpha": (8, 13), "beta": (13, 30)}


def s3c():
    import boto3
    from botocore.config import Config
    return boto3.Session(profile_name="physionet").client(
        "s3", region_name="us-east-1",
        config=Config(s3={"payload_signing_enabled": False}, max_pool_connections=32,
                      retries={"max_attempts": 3}))


_BP = {}


def bp(fs):
    from scipy.signal import butter
    if fs not in _BP:
        _BP[fs] = butter(4, [0.5 / (fs / 2), 40.0 / (fs / 2)], btype="band")
    return _BP[fs]


def parse_hea(txt):
    lines = [l for l in txt.splitlines() if l.strip()]
    nsig = int(lines[0].split()[1]); fs = float(lines[0].split()[2])
    gains, bases, names = [], [], []
    for l in lines[1:1 + nsig]:
        p = l.split()
        m = re.match(r"([-\d.eE+]+)\(?(-?\d+)?\)?", p[2])
        g = float(m.group(1)); b = float(m.group(2) or 0)
        gains.append(g if g != 0 else 1.0); bases.append(b); names.append(p[-1])
    return fs, gains, bases, names


def spectral(x, fs):
    """Relative band powers over the WHOLE record, plus the same restricted to non-suppressed frames."""
    from scipy.signal import welch
    if len(x) < fs * 20:
        return None

    def rel(sig):
        if len(sig) < fs * 5:
            return None
        f, P = welch(sig, fs=fs, nperseg=int(min(len(sig), fs * 4)))
        m = (f >= 1) & (f <= 30)
        tot = float(P[m].sum())
        if tot <= 0:
            return None
        out = {}
        for k, (lo, hi) in BANDS.items():
            b = (f >= lo) & (f < hi)
            out[k] = float(P[b].sum() / tot)
        # spectral edge: frequency below which 95 % of 1-30 Hz power lies
        c = np.cumsum(P[m]) / tot
        out["sef95"] = float(f[m][np.searchsorted(c, 0.95)]) if c[-1] >= 0.95 else 30.0
        out["slow_frac"] = out["delta"] + out["theta"]
        return out

    whole = rel(x)
    if whole is None:
        return None

    # suppression mask, same detector as everywhere else in this project
    fr = max(1, int(FRAME_S * fs)); n = len(x) // fr
    seg = x[:n * fr].reshape(n, fr)
    ptp = seg.max(1) - seg.min(1)
    dead = ptp < 1e-9
    supp = (ptp < THRESH) & (~dead)
    need = max(1, int(MIN_RUN_S / FRAME_S)); run = 0; sup = supp.copy()
    for i in range(n):
        if supp[i]:
            run += 1
        else:
            if run < need:
                sup[max(0, i - run):i] = False
            run = 0
    burden = float(sup.sum() / max(1, (~dead).sum()))
    keep = np.repeat(~sup & ~dead, fr)[:n * fr]
    nonsupp = rel(x[:n * fr][keep]) if keep.sum() > fs * 5 else None

    out = {f"w_{k}": v for k, v in whole.items()}
    out["burden"] = burden
    if nonsupp:
        out.update({f"b_{k}": v for k, v in nonsupp.items()})
    return out


def one_patient(pid, s3):
    import scipy.io as sio
    from scipy.signal import filtfilt
    try:
        r = s3.list_objects_v2(Bucket=AP, Prefix=f"{ROOT}{pid}/", MaxKeys=1000)
        eeg = [o["Key"] for o in r.get("Contents", []) if o["Key"].endswith("_EEG.mat")]
        if not eeg:
            return None

        def hr(k):
            m = re.match(r"^\d+_\d+_(\d+)_EEG\.mat$", k.split("/")[-1])
            return int(m.group(1)) if m else 10 ** 6
        eeg.sort(key=lambda k: abs(hr(k) - HOUR))
        key = eeg[0]; hour = hr(key)
        hea = s3.get_object(Bucket=AP, Key=key[:-4] + ".hea")["Body"].read().decode("utf-8", "replace")
        fs, gains, bases, names = parse_hea(hea)
        val = sio.loadmat(io.BytesIO(s3.get_object(Bucket=AP, Key=key)["Body"].read()))["val"]
        idx = {n.upper(): i for i, n in enumerate(names)}
        b, a = bp(fs)
        feats = []
        for u, v in PAIRS:
            if u in idx and v in idx:
                iu, iv = idx[u], idx[v]
                d = ((val[iu].astype(np.float64) - bases[iu]) / gains[iu]
                     - (val[iv].astype(np.float64) - bases[iv]) / gains[iv])
                if len(d) > 100:
                    try:
                        m = spectral(filtfilt(b, a, d), fs)
                        if m:
                            feats.append(m)
                    except Exception:
                        pass
        if not feats:
            return None
        keys = set().union(*[set(f) for f in feats])
        out = {}
        for k in keys:
            vals = [f[k] for f in feats if k in f and f[k] == f[k]]
            out[k] = float(np.median(vals)) if vals else float("nan")
        out.update(pid=pid, hour=hour, fs=fs)
        return out
    except Exception:
        return None


COLS = ["pid", "hour", "burden", "w_delta", "w_theta", "w_alpha", "w_beta", "w_sef95", "w_slow_frac",
        "b_delta", "b_theta", "b_alpha", "b_beta", "b_sef95", "b_slow_frac", "fs"]


def main():
    coh = [r["pid"] for r in csv.DictReader(open("/tmp/eeg_probe/icare_cohort.csv"))]
    done = set()
    if os.path.exists(OUT):
        done = {r["pid"] for r in csv.DictReader(open(OUT))}
    todo = [p for p in coh if p not in done]
    print(f"I-CARE background spectra at ~hour {HOUR:.0f}: {len(todo)} to do ({len(done)} done)")
    newf = not os.path.exists(OUT)
    fh = open(OUT, "a", newline=""); w = csv.writer(fh)
    if newf:
        w.writerow(COLS); fh.flush()
    s3 = s3c(); n = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        for res in ex.map(lambda p: one_patient(p, s3), todo):
            if res:
                w.writerow([res.get(c, "") for c in COLS]); n += 1
            if n and n % 25 == 0:
                fh.flush(); print(f"  {n} written", flush=True)
    fh.close(); print(f"DONE {n} -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
