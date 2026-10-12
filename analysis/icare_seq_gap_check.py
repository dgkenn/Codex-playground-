#!/usr/bin/env python3
"""Does the usable-frame mask distort the time axis of the suppression series?

THE CONCERN, found by reading our own extraction code rather than by a failure. `icare_topography.py` drops
frames where most derivations are flat-line dead, then forms 1-second bins from what REMAINS:

    usable = ok & (nalive * 2 > len(supp_stack))
    fsupp  = frame_supp[usable][:nb * FRAMES_PER_BIN].reshape(nb, FRAMES_PER_BIN)

If the dropped frames are at the edges of the recording this is a harmless trim. If they are INTERIOR, the
surviving frames are glued together and the series silently becomes non-uniformly sampled in time -- which is
fine for a burden (an average over frames, order-free) and NOT fine for BSP, whose entire content is a model of
how the state evolves from one bin to the next. A gap glued shut looks to the estimator like an abrupt jump.

This is precisely rule 5's shape in reverse: the extraction did not fail, produced plausible output, and would
have been believed. So we measure the thing rather than assume it.

REPORTED: the fraction of frames dropped, whether the drops are edge or interior, and the largest interior gap.
The decision rule is fixed here before looking: if the median interior-dropped fraction is under 1 % and the
largest interior gap is under 2 s, the glue is immaterial for a 1-second-bin random-walk model and the series
is used as extracted. Otherwise the BSP real-data analysis must be restricted to recordings with no interior
gaps.
"""
import csv, io, os, re, sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from icare_topography import (AP, ROOT, PAIRS, THRESH, FRAME_S, MIN_RUN_S, HOUR,
                              s3c, bp, parse_hea, suppression_frames)

NCHECK = int(os.environ.get("GAP_NCHECK", "24"))


def one(pid, s3):
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
        key = eeg[0]
        hea = s3.get_object(Bucket=AP, Key=key[:-4] + ".hea")["Body"].read().decode("utf-8", "replace")
        fs, gains, bases, names = parse_hea(hea)
        val = sio.loadmat(io.BytesIO(s3.get_object(Bucket=AP, Key=key)["Body"].read()))["val"]
        idx = {n.upper(): i for i, n in enumerate(names)}
        b, a = bp(fs)
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
                s, dd = suppression_frames(filtfilt(b, a, d), fs)
            except Exception:
                continue
            if s is not None:
                supp_stack.append(s); dead_stack.append(dd)
        if not supp_stack:
            return None
        L = min(len(s) for s in supp_stack)
        D = np.stack([d[:L] for d in dead_stack])
        alive = ~D
        nalive = alive.sum(0)
        usable = (nalive > 0) & (nalive * 2 > len(supp_stack))
        tot = L
        drop = int((~usable).sum())
        # split edge drops from interior drops
        first = int(np.argmax(usable)) if usable.any() else L
        last = int(L - np.argmax(usable[::-1])) if usable.any() else 0
        edge = first + (L - last)
        interior = drop - edge
        # largest interior run of dropped frames
        mx = 0
        if usable.any():
            run = 0
            for i in range(first, last):
                if not usable[i]:
                    run += 1; mx = max(mx, run)
                else:
                    run = 0
        return dict(pid=pid, frames=tot, dur_s=tot * FRAME_S, drop_frac=drop / tot,
                    edge_frac=edge / tot, interior_frac=interior / tot, max_gap_s=mx * FRAME_S)
    except Exception:
        return None


def main():
    pids = [r["pid"] for r in csv.DictReader(open("/tmp/eeg_probe/icare_cohort.csv"))]
    rng = np.random.default_rng(7)
    sel = [pids[i] for i in rng.choice(len(pids), min(NCHECK, len(pids)), replace=False)]
    s3 = s3c()
    with ThreadPoolExecutor(max_workers=6) as ex:
        res = [r for r in ex.map(lambda p: one(p, s3), sel) if r]
    assert res, "no recording could be re-read -- the check itself failed, which is not a pass"
    print(f"re-read {len(res)} randomly chosen recordings of {len(sel)} attempted\n")
    print(f"{'pid':>6} {'duration s':>11} {'dropped':>9} {'edge':>8} {'interior':>9} {'max gap s':>10}")
    print("-" * 60)
    for r in sorted(res, key=lambda r: -r["interior_frac"])[:12]:
        print(f"{r['pid']:>6} {r['dur_s']:>11.0f} {100*r['drop_frac']:>8.2f}% {100*r['edge_frac']:>7.2f}% "
              f"{100*r['interior_frac']:>8.2f}% {r['max_gap_s']:>10.1f}")
    med_int = float(np.median([r["interior_frac"] for r in res]))
    mx_int = float(np.max([r["interior_frac"] for r in res]))
    mx_gap = float(np.max([r["max_gap_s"] for r in res]))
    print(f"\n   interior-dropped fraction: median {100*med_int:.3f}%, worst {100*mx_int:.2f}%")
    print(f"   largest interior gap anywhere: {mx_gap:.1f} s")
    print(f"   median duration {np.median([r['dur_s'] for r in res]):.0f} s")
    ok = med_int < 0.01 and mx_gap < 2.0
    print(f"\n   VERDICT: {'immaterial -- use the series as extracted' if ok else 'MATERIAL -- the BSP real-data analysis must exclude recordings with interior gaps'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
