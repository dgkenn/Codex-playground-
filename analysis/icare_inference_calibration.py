#!/usr/bin/env python3
"""Negative control: do our two inference procedures have the false-positive rate they claim?

WHY THIS EXISTS, and it is not routine. Shaking out `icare_topo_test.py` on PERMUTED outcome labels -- where
every association is destroyed by construction and every test must be null -- the primary arm reported a
difference of -0.033 [-0.076, -0.004], a 95 % bootstrap interval EXCLUDING ZERO on data with no signal in it.
One such event among six tests is unremarkable on its own. Assuming so is exactly the move rule 23 of the error
catalogue exists to prevent: self-written code and self-written tests share blind spots, and every headline
number in this project -- the +0.062 [+0.032, +0.095] increment included -- is produced by one of the two
procedures checked here. If either is anti-conservative, several reported intervals are too narrow.

So we measure the false-positive rate directly rather than reasoning about it. Under permuted labels the
correct rejection rate is 0.05 for a nominal 95 % interval.

  C1  `diff_ci` -- percentile bootstrap for a difference in group means.
  C2  `oob_increment` -- out-of-bag bootstrap for an AUC increment, the procedure behind the headline result.
      Its null is one-sided in practice: we report an increment as real when the lower bound exceeds zero, so
      the rate that matters is P(lower bound > 0), which should be about 0.025.

REAL FEATURES, PERMUTED LABELS. The features are the real extracted ones, so their true distributions,
skewness, outliers and mutual correlations are preserved -- only the link to outcome is destroyed. A Gaussian
simulation would not test the procedures on the data they are actually applied to.
"""
import csv, os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from icare_morph_replication import oob_increment
from icare_topo_test import diff_ci, load_num

COHORT = os.environ.get("ICARE_COHORT", "/tmp/eeg_probe/icare_cohort.csv")
TOPO = os.environ.get("ICARE_TOPO_OUT", "/tmp/eeg_probe/icare_topo.csv")
BG = os.environ.get("ICARE_BG_OUT", "/tmp/eeg_probe/icare_background.csv")
MORPH = os.environ.get("ICARE_MORPH_OUT", "/tmp/eeg_probe/icare_morph2.csv")
NPERM_DIFF = int(os.environ.get("NPERM_DIFF", "400"))
NPERM_OOB = int(os.environ.get("NPERM_OOB", "60"))
NBOOT = int(os.environ.get("NBOOT", "600"))
OOB_REPS = int(os.environ.get("OOB_REPS", "200"))


def main():
    rng = np.random.default_rng(20260727)
    coh = {}
    for r in csv.DictReader(open(COHORT)):
        pid = (r.get("pid") or "").strip()
        try:
            cpc = float(r.get("cpc"))
        except (TypeError, ValueError):
            continue
        if pid and cpc == cpc:
            coh[pid] = 1.0 if cpc >= 3 else 0.0

    topo = load_num(TOPO, ["ap_slow_grad", "slow_sd", "lr_asym", "burden"])
    bg = load_num(BG, ["w_slow_frac"])
    morph = load_num(MORPH, ["alpha_beta"])
    assert topo and bg and morph, "one of the feature tables is empty -- check the extraction"

    pids = sorted(p for p in topo if p in coh)
    y = np.array([coh[p] for p in pids])
    n = len(y)
    print(f"negative control on {n:,} patients with real features and permuted labels "
          f"(poor outcome {100*y.mean():.1f}%)")
    assert n >= 150, "too few patients for a calibration check"

    # ---- C1 --------------------------------------------------------------------------------------
    feats = {k: np.array([topo[p][k] for p in pids]) for k in ("ap_slow_grad", "slow_sd", "lr_asym")}
    print("\n" + "=" * 88)
    print(f"C1  diff_ci FALSE-POSITIVE RATE, {NPERM_DIFF} permutations x {NBOOT} bootstrap draws")
    print("=" * 88)
    print(f"{'feature':>14} {'rejections':>12} {'rate':>8} {'nominal':>9}  {'verdict':>16}")
    print("-" * 88)
    worst = 0.0
    for name, v in feats.items():
        rej = 0
        for _ in range(NPERM_DIFF):
            yp = rng.permutation(y)
            lo, hi = diff_ci(v, yp, rng, NBOOT)
            if lo == lo and (lo > 0 or hi < 0):
                rej += 1
        rate = rej / NPERM_DIFF
        worst = max(worst, rate)
        se = np.sqrt(0.05 * 0.95 / NPERM_DIFF)
        ok = abs(rate - 0.05) <= 3 * se
        print(f"{name:>14} {rej:>7}/{NPERM_DIFF:<4} {rate:>8.3f} {0.05:>9.3f}  "
              f"{'calibrated' if ok else 'MISCALIBRATED':>16}")
    print(f"\n  Monte-Carlo SE at {NPERM_DIFF} permutations is "
          f"{np.sqrt(0.05*0.95/NPERM_DIFF):.3f}; a rate inside 0.05 +/- 3 SE is consistent with nominal.")

    # ---- C2 --------------------------------------------------------------------------------------
    tri = sorted(p for p in pids if p in bg and p in morph)
    m = len(tri)
    yy = np.array([coh[p] for p in tri])
    o = np.ones(m)
    bur = np.array([topo[p]["burden"] for p in tri])
    slw = np.array([bg[p]["w_slow_frac"] for p in tri])
    ab = np.array([morph[p]["alpha_beta"] for p in tri])
    blk = np.column_stack([np.array([topo[p][k] for p in tri]) for k in
                           ("ap_slow_grad", "slow_sd", "lr_asym")])
    Xa = np.column_stack([o, bur, slw, ab])
    Xb = np.column_stack([Xa, blk])

    print("\n" + "=" * 88)
    print(f"C2  oob_increment FALSE-POSITIVE RATE, {NPERM_OOB} permutations x {OOB_REPS} out-of-bag reps "
          f"on {m:,} patients")
    print("=" * 88)
    incs, pos, neg = [], 0, 0
    for i in range(NPERM_OOB):
        yp = rng.permutation(yy)
        if not (0 < yp.sum() < m):
            continue
        inc, lo, hi, k = oob_increment(Xa, Xb, yp, rng, reps=OOB_REPS)
        if inc == inc:
            incs.append(inc)
            if lo == lo and lo > 0:
                pos += 1
            if hi == hi and hi < 0:
                neg += 1
        if (i + 1) % 20 == 0:
            print(f"   {i+1}/{NPERM_OOB} permutations", flush=True)
    k = len(incs)
    assert k >= 20, "too few usable permutations for C2"
    rate1 = pos / k
    se1 = np.sqrt(0.025 * 0.975 / k)
    print(f"\n   usable permutations {k}")
    print(f"   mean increment under the null {np.mean(incs):+.4f}  "
          f"(should be about zero; a positive bias would inflate every reported increment)")
    print(f"   lower bound > 0 in {pos}/{k} = {rate1:.3f}   nominal 0.025   "
          f"{'calibrated' if abs(rate1 - 0.025) <= 3 * se1 else 'MISCALIBRATED'}")
    print(f"   upper bound < 0 in {neg}/{k} = {neg/k:.3f}   nominal 0.025")
    print(f"   Monte-Carlo SE {se1:.3f}")

    print("\n" + "=" * 88)
    print("WHAT THIS LICENSES")
    print("=" * 88)
    print("   If both procedures are calibrated, the permuted-label rejection that prompted this check was an")
    print("   ordinary false positive and the reported intervals stand as written. If either is not, every")
    print("   interval produced by it -- including the headline out-of-bag increment -- is too narrow and must")
    print("   be widened or replaced before anything is reported.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
