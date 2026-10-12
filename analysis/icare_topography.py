#!/usr/bin/env python3
"""One S3 pass, two open questions: spatial distribution, and second-by-second suppression.

BOTH of these are named in the record as the obvious next experiments, and both need the same raw signal, so
they share one extraction rather than two.

------------------------------------------------------------------------------------------------------------
QUESTION 1 -- TOPOGRAPHY.  R360 left a residual: the clinician's "generalized slowing" flag carries
-0.752 [-1.075, -0.434] beyond suppression burden AND our intra-burst 8-30 Hz measure, and B3 then showed the
whole-record background measure does not explain it either (the two spectral measures are mutually redundant).
The ledger names four unmeasured candidates. **Spatial distribution is the one this schema can actually
measure**: every spectral feature this project has computed takes a MEDIAN ACROSS CHANNELS and therefore
throws topography away by construction. A human reading a record does not.

  REGISTERED, before the data was looked at:
  T1  ANTERIOR-POSTERIOR GRADIENT.  Relative slow power falls from front to back in a brain with a preserved
      posterior faster background; diffuse injury flattens that gradient. So (frontal slow - posterior slow)
      is HIGHER in good outcome.
  T2  SPATIAL DISPERSION.  Across-channel SD of relative slow power is LOWER in poor outcome -- a uniformly
      injured cortex slows uniformly.
  T3  DECISIVE.  Topographic measures carry outcome information after adjusting for burden AND whole-record
      slow fraction AND intra-burst 8-30 Hz content.  FALSIFIED IF they add nothing -- in which case the
      spatial dimension is not what the human reader is seeing either, and three of the four named candidates
      are down to two.

  THE LIMIT THAT TRAVELS WITH THIS, stated up front. The clinician flag lives in HEEDB; I-CARE has no such
  flag. So this CANNOT directly test "topography explains the flag residual". It tests the necessary
  condition: that spatial information carries outcome signal the non-spatial measures do not. If that fails,
  the flag hypothesis fails with it. If it holds, it is suggestive and not confirmatory.

------------------------------------------------------------------------------------------------------------
QUESTION 2 -- BSP WINDOW LENGTH.  `47_BSP_TECHNICAL_NOTE.md` Sec. 5.3 states the limitation verbatim:
"r = 0.988 is specific to whole-recording aggregation. Shorter windows would give BSP more room, and we have
not characterised where the equivalence breaks down as window length falls -- that is the obvious next
experiment and it is directly answerable with this code."  It is answerable only with a SECOND-BY-SECOND
suppression series, which no cached file holds -- `icare_bsp.csv` stores summaries only. So we persist the
per-second counts here and sweep window length offline in `analysis/bsp_window_sweep.py`.

------------------------------------------------------------------------------------------------------------
DETECTOR. Identical to every other suppression measurement in this project (0.1 s frames, 8 uV peak-to-peak,
runs of >=0.5 s, bipolar longitudinal montage) so the numbers are comparable across experiments. A frame counts
as suppressed when the MAJORITY of channel pairs are suppressed, which is the binary analogue of the
median-across-channels rule used for the continuous features.
"""
import csv, io, os, re, sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np

AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-restricted-access-point"
ROOT = "ICARE_train/training/"
OUT = os.environ.get("ICARE_TOPO_OUT", "/tmp/eeg_probe/icare_topo.csv")
SEQ = os.environ.get("ICARE_SEQ_OUT", "/tmp/eeg_probe/icare_suppseq.csv")
HOUR = float(os.environ.get("ICARE_HOUR", "24"))
THRESH = float(os.environ.get("ICARE_THRESH", "8.0"))
FRAME_S, MIN_RUN_S = 0.1, 0.5
FRAMES_PER_BIN = 10  # 1-second bins, the resolution the BSP paper reports

# Bipolar longitudinal chains, kept in anterior -> posterior order within each hemisphere.
PAIRS = [("FP1", "F3"), ("F3", "C3"), ("C3", "P3"), ("P3", "O1"),
         ("FP2", "F4"), ("F4", "C4"), ("C4", "P4"), ("P4", "O2")]
# Region assignment for the anterior-posterior gradient. "Frontal" is the two most anterior derivations of
# each chain; "posterior" the two most posterior. The middle pair of each chain is deliberately not used in
# the gradient so that the two ends do not share a channel.
FRONTAL = {"FP1-F3", "FP2-F4"}
POSTERIOR = {"P3-O1", "P4-O2"}
LEFT = {"FP1-F3", "F3-C3", "C3-P3", "P3-O1"}
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


def suppression_frames(x, fs):
    """Frame-level boolean suppression for one derivation, plus the dead-channel mask."""
    fr = max(1, int(FRAME_S * fs)); n = len(x) // fr
    if n < 10:
        return None, None
    seg = x[:n * fr].reshape(n, fr)
    ptp = seg.max(1) - seg.min(1)
    dead = ptp < 1e-9
    supp = (ptp < THRESH) & (~dead)
    need = max(1, int(MIN_RUN_S / FRAME_S)); run = 0; out = supp.copy()
    for i in range(n):
        if supp[i]:
            run += 1
        else:
            if run < need:
                out[max(0, i - run):i] = False
            run = 0
    return out, dead


def rel_spectrum(sig, fs):
    from scipy.signal import welch
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
    c = np.cumsum(P[m]) / tot
    out["sef95"] = float(f[m][np.searchsorted(c, 0.95)]) if c[-1] >= 0.95 else 30.0
    out["slow_frac"] = out["delta"] + out["theta"]
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

        per_pair = {}     # "FP1-F3" -> relative spectrum
        supp_stack, dead_stack = [], []
        for u, v in PAIRS:
            if u not in idx or v not in idx:
                continue
            iu, iv = idx[u], idx[v]
            d = ((val[iu].astype(np.float64) - bases[iu]) / gains[iu]
                 - (val[iv].astype(np.float64) - bases[iv]) / gains[iv])
            if len(d) <= 100:
                continue
            try:
                d = filtfilt(b, a, d)
            except Exception:
                continue
            sp = rel_spectrum(d, fs)
            if sp:
                per_pair[f"{u}-{v}"] = sp
            s, dd = suppression_frames(d, fs)
            if s is not None:
                supp_stack.append(s); dead_stack.append(dd)

        if len(per_pair) < 4 or not supp_stack:
            return None

        # ---- suppression series: majority vote across pairs, then 1-second bins -----------------------
        L = min(len(s) for s in supp_stack)
        S = np.stack([s[:L] for s in supp_stack]); D = np.stack([d[:L] for d in dead_stack])
        alive = ~D
        # a frame is suppressed if a majority of the pairs that are alive there call it suppressed
        nalive = alive.sum(0)
        frame_supp = np.zeros(L, bool)
        ok = nalive > 0
        frame_supp[ok] = (S & alive).sum(0)[ok] * 2 > nalive[ok]
        usable = ok & (nalive * 2 > len(supp_stack))   # drop frames where most pairs are dead
        nb = int(usable.sum()) // FRAMES_PER_BIN
        counts = []
        if nb >= 4:
            fsupp = frame_supp[usable][:nb * FRAMES_PER_BIN].reshape(nb, FRAMES_PER_BIN)
            counts = fsupp.sum(1).astype(int).tolist()
        burden = float(frame_supp[usable].mean()) if usable.any() else float("nan")

        # ---- topography ------------------------------------------------------------------------------
        def agg(keys, field):
            v = [per_pair[k][field] for k in keys if k in per_pair]
            return float(np.mean(v)) if v else float("nan")

        allp = list(per_pair)
        slow_all = np.array([per_pair[k]["slow_frac"] for k in allp])
        sef_all = np.array([per_pair[k]["sef95"] for k in allp])
        fslow, pslow = agg(FRONTAL, "slow_frac"), agg(POSTERIOR, "slow_frac")
        fsef, psef = agg(FRONTAL, "sef95"), agg(POSTERIOR, "sef95")
        lslow = agg([k for k in allp if k in LEFT], "slow_frac")
        rslow = agg([k for k in allp if k not in LEFT], "slow_frac")
        return dict(
            pid=pid, hour=hour, fs=fs, burden=burden, n_pairs=len(per_pair), n_bins=nb,
            ap_slow_grad=fslow - pslow,          # T1
            ap_sef_grad=psef - fsef,             # faster posteriorly = positive, same direction as T1
            slow_sd=float(np.std(slow_all)),     # T2
            sef_sd=float(np.std(sef_all)),
            slow_range=float(slow_all.max() - slow_all.min()),
            lr_asym=abs(lslow - rslow),
            frontal_slow=fslow, posterior_slow=pslow, med_slow=float(np.median(slow_all)),
            med_sef=float(np.median(sef_all)), _counts=counts)
    except Exception:
        return None


COLS = ["pid", "hour", "burden", "n_pairs", "n_bins", "ap_slow_grad", "ap_sef_grad", "slow_sd", "sef_sd",
        "slow_range", "lr_asym", "frontal_slow", "posterior_slow", "med_slow", "med_sef", "fs"]


def main():
    coh = [r["pid"] for r in csv.DictReader(open("/tmp/eeg_probe/icare_cohort.csv"))]
    done = set()
    if os.path.exists(OUT):
        done = {r["pid"] for r in csv.DictReader(open(OUT))}
    todo = [p for p in coh if p not in done]
    print(f"I-CARE topography + suppression series at ~hour {HOUR:.0f}: "
          f"{len(todo)} to do ({len(done)} done)", flush=True)
    newf = not os.path.exists(OUT)
    fh = open(OUT, "a", newline=""); w = csv.writer(fh)
    sq = open(SEQ, "a", newline=""); ws = csv.writer(sq)
    if newf:
        w.writerow(COLS); ws.writerow(["pid", "counts_per_second"]); fh.flush(); sq.flush()
    s3 = s3c(); n = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        for res in ex.map(lambda p: one_patient(p, s3), todo):
            if res:
                w.writerow([res.get(c, "") for c in COLS])
                if res["_counts"]:
                    ws.writerow([res["pid"], " ".join(str(c) for c in res["_counts"])])
                n += 1
            if n and n % 25 == 0:
                fh.flush(); sq.flush(); print(f"  {n} written", flush=True)
    fh.close(); sq.close()
    print(f"DONE {n} -> {OUT} and {SEQ}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
