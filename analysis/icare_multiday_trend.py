#!/usr/bin/env python3
"""Does suppression burden's change ACROSS DAYS carry outcome information the level does not?

WHY THIS EXISTS. `icare_temporal_evolution.py` tested the trend WITHIN one hour-long recording and falsified
it: the trend term was -0.478 [-1.645, +0.748], not distinguishable from zero, and it added nothing over the
level (out-of-bag -0.002 [-0.030, +0.009]). That result came with its scope stated in advance -- one hour at
roughly hour 24 cannot show the trend a clinician actually reads, which runs over days. This is that test, at
the scale where the hypothesis was always plausible, and it is the last of the four candidates for the
clinician-flag residual that this schema can measure.

Burden is already cached at four target hours (12, 24, 36, 48) from a previous pass, so this costs no new
extraction.

------------------------------------------------------------------------------------------------------------
THE TRAP THIS IS BUILT AROUND, found by checking rather than by being bitten. The cached files record the
ACTUAL hour of the recording nearest each target, not the target itself. A patient with few recordings gets
the SAME file selected for several targets: **15.4 % of h12/h24 pairs are the identical recording**, for which
the change is exactly zero by construction. Including them would have loaded the sample with structural zeros,
diluted the estimate toward the null, and produced a negative result that looked like biology. Pairs are
therefore required to be genuinely separated in time, and the change is expressed per 24 h using the ACTUAL
elapsed hours rather than the nominal ones.

------------------------------------------------------------------------------------------------------------
REGISTERED, before the data was looked at.

  M1  DIRECTION. Burden FALLS from early to late in good outcome and does not in poor outcome, so the change
      per 24 h (late minus early) is HIGHER in poor outcome.
  M2  DECISIVE, a sign test for the same reason as before (catalogue rule 12): decompose into the MEAN of the
      two measurements and their DIFFERENCE, and require the difference term's coefficient to exclude zero
      WITH THE PREDICTED SIGN. Two noisy measurements of a constant level average to a better estimate than
      one, so an increment alone would not distinguish trend information from noise reduction. A
      correctly-signed coefficient cannot be produced by averaging.
  M3  SURVIVORSHIP, checked rather than assumed. A late recording exists only for a patient who lived long
      enough to be recorded, and the patients who die early are the poor-outcome ones. If availability is
      outcome-related -- and it almost certainly is -- then this estimand is "the trend among patients who
      survived to be measured twice", which is a real but restricted question. Reported either way.

PRIMARY is the h12 -> h48 contrast, pre-declared here: the longer time base carries more trend signal.
SECONDARY is h12 -> h24, which conditions on survival less severely. Both are reported whatever they show.
"""
import csv, os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from icare_morph_replication import logit_fit, auc, cv_auc, oob_increment

D = "/tmp/eeg_probe"
COHORT = os.environ.get("ICARE_COHORT", f"{D}/icare_cohort.csv")
NBOOT = int(os.environ.get("NBOOT", "800"))
MIN_GAP_PRIMARY = float(os.environ.get("MIN_GAP", "24"))    # hours, h12 -> h48
MIN_GAP_SECONDARY = 6.0                                      # hours, h12 -> h24


def load_burden(fn):
    out = {}
    for r in csv.DictReader(open(f"{D}/{fn}")):
        pid = (r.get("pid") or "").strip()
        try:
            hour, bs = float(r["hour"]), float(r["bs"])
        except (KeyError, TypeError, ValueError):
            continue
        if pid and hour == hour and bs == bs:
            out[pid] = (hour, bs)
    return out


def boot_coef(X, y, col, rng, reps):
    out, n = [], len(y)
    for _ in range(reps):
        i = rng.integers(0, n, n)
        if 0 < y[i].sum() < n:
            try:
                out.append(float(logit_fit(X[i], y[i])[col]))
            except Exception:
                continue
    if len(out) < 50:
        return float("nan"), float("nan")
    return tuple(np.percentile(out, [2.5, 97.5]))


def boot_diff(x, y, rng, reps):
    n, bs = len(y), []
    for _ in range(reps):
        i = rng.integers(0, n, n)
        a0, a1 = x[i][y[i] == 0], x[i][y[i] == 1]
        if len(a0) > 10 and len(a1) > 10:
            bs.append(a1.mean() - a0.mean())      # poor minus good, matching M1
    if len(bs) < 50:
        return float("nan"), float("nan")
    return tuple(np.percentile(bs, [2.5, 97.5]))


def arm(name, early, late, min_gap, coh, rng):
    print("\n" + "=" * 96)
    print(f"{name}   (minimum genuine separation {min_gap:.0f} h)")
    print("=" * 96)
    pairs = [p for p in early if p in late and p in coh]
    same = sum(1 for p in pairs if early[p][0] == late[p][0])
    ok = [p for p in pairs if (late[p][0] - early[p][0]) >= min_gap]
    print(f"   patients with both measurements: {len(pairs):,}   "
          f"identical recording (change is zero by construction): {same:,}   "
          f"usable after the separation requirement: {len(ok):,}")
    if len(ok) < 150:
        print("   too few usable pairs")
        return

    # ---- M3: is having a usable late recording outcome-related? -----------------------------------
    ya = np.array([coh[p] for p in pairs])
    yu = np.array([coh[p] for p in ok])
    excl = [p for p in pairs if p not in set(ok)]
    if excl:
        ye = np.array([coh[p] for p in excl])
        bs = [float(np.mean(rng.choice(yu, len(yu)))) - float(np.mean(rng.choice(ye, len(ye))))
              for _ in range(1000)]
        lo, hi = np.percentile(bs, [2.5, 97.5])
        print(f"   M3 survivorship: usable {100*yu.mean():.1f}% poor vs excluded {100*ye.mean():.1f}% poor, "
              f"difference {100*(yu.mean()-ye.mean()):+.1f} pp [{100*lo:+.1f},{100*hi:+.1f}]")
        print(f"      {'availability is NOT outcome-related' if lo < 0 < hi else 'AVAILABILITY IS OUTCOME-RELATED -- the estimand is the trend among patients measured twice'}")

    y = yu
    he = np.array([early[p][0] for p in ok]); hl = np.array([late[p][0] for p in ok])
    be = np.array([early[p][1] for p in ok]); bl = np.array([late[p][1] for p in ok])
    gap = hl - he
    rate = (bl - be) / gap * 24.0            # change in burden per 24 h, using ACTUAL elapsed time
    mean2 = (be + bl) / 2.0
    n = len(y)
    print(f"   poor outcome {100*y.mean():.1f}%   median actual gap {np.median(gap):.0f} h   "
          f"mean burden {mean2.mean():.3f}")

    # ---- M1 ---------------------------------------------------------------------------------------
    d = rate[y == 1].mean() - rate[y == 0].mean()
    lo, hi = boot_diff(rate, y, rng, NBOOT)
    print(f"\n   M1  change in burden per 24 h:  good {rate[y==0].mean():+.4f}   poor {rate[y==1].mean():+.4f}")
    print(f"       difference (poor - good) {d:+.4f} [{lo:+.4f},{hi:+.4f}]   "
          f"{'CONFIRMED' if lo > 0 else ('REVERSED -- burden rises more in GOOD outcome' if hi < 0 else 'null')}")
    a = auc(y, rate)
    print(f"       AUC of the trend alone {max(a, 1-a):.3f}   "
          f"(mean level alone {max(auc(y, mean2), 1-auc(y, mean2)):.3f})")

    # ---- M2: the decisive sign test ----------------------------------------------------------------
    one = np.ones(n)
    Xm = np.column_stack([one, mean2])
    Xmd = np.column_stack([one, mean2, rate])
    b = logit_fit(Xmd, y)
    cl, ch = boot_coef(Xmd, y, 2, rng, NBOOT)
    print(f"\n   M2  mean-burden coefficient {b[1]:+.3f}")
    print(f"       TREND coefficient       {b[2]:+.3f} [{cl:+.3f},{ch:+.3f}]")
    if cl == cl and cl * ch > 0:
        print(f"       M2 {'CONFIRMED -- excludes zero with the predicted sign' if cl > 0 else 'REVERSED -- excludes zero with the WRONG sign'}")
    else:
        print("       M2 FALSIFIED -- the trend carries no outcome information beyond the level")

    inc, l3, h3, k3 = oob_increment(Xm, Xmd, y, rng)
    print(f"\n   M3  level alone CV AUC {cv_auc(Xm, y, rng):.3f}   + trend {cv_auc(Xmd, y, rng):.3f}   "
          f"out-of-bag {inc:+.3f} [{l3:+.3f},{h3:+.3f}] ({k3} reps)")


def main():
    rng = np.random.default_rng(20260727)
    coh = {}
    for r in csv.DictReader(open(COHORT)):
        pid = (r.get("pid") or "").strip()
        try:
            c = float(r.get("cpc"))
        except (TypeError, ValueError):
            continue
        if pid and c == c:
            coh[pid] = 1.0 if c >= 3 else 0.0
    assert coh, "no outcomes loaded"

    h12, h24, h48 = load_burden("icare_bs_h12.csv"), load_burden("icare_bs.csv"), load_burden("icare_bs_h48.csv")
    assert h12 and h24 and h48, "a cached burden file is empty"
    print(f"cached burden measurements: h12 {len(h12):,}   h24 {len(h24):,}   h48 {len(h48):,}")

    arm("PRIMARY -- hour 12 to hour 48", h12, h48, MIN_GAP_PRIMARY, coh, rng)
    arm("SECONDARY -- hour 12 to hour 24", h12, h24, MIN_GAP_SECONDARY, coh, rng)
    return 0


if __name__ == "__main__":
    sys.exit(main())
