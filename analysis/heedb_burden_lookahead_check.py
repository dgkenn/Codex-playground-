#!/usr/bin/env python3
"""How much of the headline result is exposed to look-ahead in the burden definition?

THE PROBLEM. `heedb_vs_guideline.py` -- the script behind the main result -- starts the outcome clock at the
patient's EARLIEST recording (line 156) but defines the exposure as the MAXIMUM burden over ALL of that
patient's recordings (line 121). Those two conventions do not agree. A patient who dies on day two has only
day-zero-to-two recordings in which to accrue a maximum; a patient who lives for months may have a dozen more.
The exposure window is therefore a function of survival, which is look-ahead: the predictor uses information
that did not exist at the moment the prediction is nominally being made.

DIRECTION. The bias is expected to be CONSERVATIVE. Extra recordings can only raise a maximum, and it is the
survivors who get the extra recordings, so survivors' burden is inflated relative to the early deaths' -- which
works AGAINST the observed gradient rather than creating it. But "expected to be conservative" is an argument,
not a measurement, and a reviewer is entitled to the measurement.

WHAT DECIDES IT. If almost every patient contributes exactly one burden measurement, then max-over-all and
value-at-index are the same number for almost everyone and the issue is immaterial -- provably, not
arguably. If many patients contribute several, the exposed fraction has to be quantified and the analysis
re-run on index-only burden.

  L1  What fraction of patients with a measured burden have more than one measurement?
  L2  Among those, how far is the maximum above the value at the earliest recording?
  L3  What fraction of ALL patients have a maximum that comes from a recording OTHER than their earliest --
      i.e. for how many could the reported exposure differ from the index-recording exposure at all?

Session identifiers increase within a patient, so the lowest session number is used as the index. This needs no
S3 access and no EEG metadata: it is a property of the burden extraction alone.
"""
import csv, glob, os, sys
from collections import defaultdict

import numpy as np

BURDEN = os.environ.get("BURDEN_GLOB", "/tmp/eeg_probe/heedb_bs_burden*.csv")


def main():
    per = defaultdict(dict)
    for f in sorted(glob.glob(BURDEN)):
        for r in csv.DictReader(open(f)):
            try:
                p = int(r["patient"]); s = int(r["session"]); v = float(r["burden"])
            except Exception:
                continue
            if v == v:
                # keep the highest value within a session, so the comparison is across sessions only
                per[p][s] = max(per[p].get(s, 0.0), v)

    n = len(per)
    if n == 0:
        print("no burden measurements found"); return 1
    multi = {p: d for p, d in per.items() if len(d) > 1}
    print(f"patients with a measured burden: {n:,}")

    print("\n" + "=" * 84)
    print("L1  HOW MANY PATIENTS CONTRIBUTE MORE THAN ONE MEASUREMENT?")
    print("=" * 84)
    cnt = defaultdict(int)
    for d in per.values():
        cnt[min(len(d), 5)] += 1
    for k in sorted(cnt):
        lab = f"{k} recordings" if k < 5 else "5 or more"
        print(f"   {lab:18s} {cnt[k]:7,d}   {100*cnt[k]/n:5.1f}%")
    print(f"\n   more than one: {len(multi):,} of {n:,} = {100*len(multi)/n:.1f}%")

    print("\n" + "=" * 84)
    print("L2  AMONG MULTI-RECORDING PATIENTS, HOW FAR IS THE MAXIMUM ABOVE THE INDEX VALUE?")
    print("=" * 84)
    if multi:
        idxv = np.array([d[min(d)] for d in multi.values()])
        maxv = np.array([max(d.values()) for d in multi.values()])
        diff = maxv - idxv
        qs = np.percentile(diff, [50, 75, 90, 99])
        print(f"   n = {len(multi):,}   mean index {idxv.mean():.3f}   mean max {maxv.mean():.3f}   "
              f"mean rise {diff.mean():+.3f}")
        print(f"   rise: median {qs[0]:.3f}   p75 {qs[1]:.3f}   p90 {qs[2]:.3f}   p99 {qs[3]:.3f}")
        print(f"   maximum already AT the index recording: {int((diff <= 1e-12).sum()):,} "
              f"({100*(diff <= 1e-12).mean():.1f}% of multi-recording patients)")
        for thr in (0.05, 0.10, 0.20):
            print(f"   rise exceeding {thr:.2f}: {int((diff > thr).sum()):,} "
                  f"({100*(diff > thr).mean():.1f}% of multi)")

    print("\n" + "=" * 84)
    print("L3  FRACTION OF THE WHOLE COHORT WHOSE REPORTED EXPOSURE COULD DIFFER FROM INDEX")
    print("=" * 84)
    moved = sum(1 for d in per.values() if max(d.values()) - d[min(d)] > 1e-12)
    print(f"   patients whose maximum comes from a later recording: {moved:,} of {n:,} = {100*moved/n:.1f}%")
    for thr in (0.05, 0.10):
        m = sum(1 for d in per.values() if max(d.values()) - d[min(d)] > thr)
        print(f"   ... and differs by more than {thr:.2f} burden: {m:,} = {100*m/n:.1f}%")

    print("\n" + "=" * 84)
    print("L4  VERDICT")
    print("=" * 84)
    frac = moved / n
    if frac < 0.05:
        print(f"   IMMATERIAL. For {100*(1-frac):.1f}% of patients the maximum IS the index measurement, so")
        print("   max-over-all and value-at-index are the same number and the look-ahead cannot be doing")
        print("   meaningful work. The headline result should still SAY which convention it used.")
    else:
        print(f"   MATERIAL. {100*frac:.1f}% of patients have a maximum drawn from a later recording. The")
        print("   guideline analysis must be re-run with burden taken at the INDEX recording only before the")
        print("   result is reported, and the two versions compared. Until then the reported AUCs describe a")
        print("   predictor that partly postdates the prediction.")
    print("\n   Either way the direction of the bias is conservative -- survivors accrue extra recordings and")
    print("   extra chances at a high maximum, which works against the observed gradient, not for it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
