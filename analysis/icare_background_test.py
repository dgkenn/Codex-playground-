#!/usr/bin/env python3
"""Does whole-record slow activity beat the intra-burst measure — and does it work where morphology cannot?

REGISTERED, before the data was looked at:
  B1  whole-record relative slow power (delta+theta / 1-30 Hz) is HIGHER in good outcome
  B2  it carries outcome information adjusted for suppression burden
  B3  DECISIVE: it carries outcome information adjusted for burden AND intra-burst 8-30 Hz content.
      FALSIFIED IF it adds nothing beyond the intra-burst measure -- then the two are the same thing and
      R360's residual was noise.
  B4  COVERAGE: these measures are defined for every recording, including near-totally suppressed ones, so
      the analysis is NOT conditioned on having four bursts. Report how many patients morphology could not
      see, and whether the background measure still discriminates among them.

B4 is the part with clinical weight. Morphology excludes 13.2 % of patients at 80 % poor outcome versus 60 %
retained -- the sickest ones -- because burst shape is undefined when there are almost no bursts. A background
measure that works there covers the patients the morphology channel structurally cannot.
"""
import csv, os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from icare_morph_replication import logit_fit, predict, auc, cv_auc, oob_increment

COHORT = os.environ.get("ICARE_COHORT", "/tmp/eeg_probe/icare_cohort.csv")
BG = os.environ.get("ICARE_BG_OUT", "/tmp/eeg_probe/icare_background.csv")
MORPH = os.environ.get("ICARE_MORPH_OUT", "/tmp/eeg_probe/icare_morph2.csv")
NBOOT = int(os.environ.get("NBOOT", "600"))


def boot_coef(X, y, col, rng, reps=600):
    out = []
    n = len(y)
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


def main():
    rng = np.random.default_rng(20260727)
    coh = {}
    for r in csv.DictReader(open(COHORT)):
        pid = (r.get("pid") or "").strip()
        try:
            cpc = float(r.get("cpc"))
        except Exception:
            continue
        if pid and cpc == cpc:
            coh[pid] = 1.0 if cpc >= 3 else 0.0

    bg = {}
    for r in csv.DictReader(open(BG)):
        pid = (r.get("pid") or "").strip()
        try:
            d = dict(slow=float(r["w_slow_frac"]), delta=float(r["w_delta"]),
                     sef=float(r["w_sef95"]), burden=float(r["burden"]))
        except Exception:
            continue
        if pid and all(v == v for v in d.values()):
            bg[pid] = d

    morph = {}
    for r in csv.DictReader(open(MORPH)):
        pid = (r.get("pid") or "").strip()
        try:
            ab = float(r["alpha_beta"])
        except Exception:
            continue
        if pid and ab == ab:
            morph[pid] = ab

    both = [p for p in bg if p in coh]
    n = len(both)
    print(f"I-CARE patients with a background spectrum and an outcome: {n:,}")
    if n < 150:
        print("*** extraction still running; rerun when it completes")
        return 1
    y = np.array([coh[p] for p in both])
    slow = np.array([bg[p]["slow"] for p in both])
    bur = np.array([bg[p]["burden"] for p in both])
    sef = np.array([bg[p]["sef"] for p in both])
    print(f"   poor outcome {100*y.mean():.1f}%")

    # ---- B1 --------------------------------------------------------------------------------------
    print("\n" + "=" * 92)
    print("B1  IS WHOLE-RECORD SLOW POWER HIGHER IN GOOD OUTCOME?")
    print("=" * 92)
    d = slow[y == 0].mean() - slow[y == 1].mean()
    bs = []
    for _ in range(NBOOT):
        i = rng.integers(0, n, n)
        a0, a1 = slow[i][y[i] == 0], slow[i][y[i] == 1]
        if len(a0) > 10 and len(a1) > 10:
            bs.append(a0.mean() - a1.mean())
    lo, hi = np.percentile(bs, [2.5, 97.5])
    print(f"   good outcome {slow[y==0].mean():.3f}   poor {slow[y==1].mean():.3f}")
    print(f"   difference (good - poor) {d:+.3f} [{lo:+.3f},{hi:+.3f}]   "
          f"{'CONFIRMED' if lo > 0 else ('REVERSED' if hi < 0 else 'null')}")
    print(f"   spectral edge: good {sef[y==0].mean():.1f} Hz   poor {sef[y==1].mean():.1f} Hz")

    # ---- B2 / B3 ---------------------------------------------------------------------------------
    one = np.ones(n)
    Xb = np.column_stack([one, bur])
    Xbs = np.column_stack([one, bur, slow])
    inc, l1, h1, k1 = oob_increment(Xb, Xbs, y, rng)
    print("\n" + "=" * 92)
    print("B2  DOES IT ADD OVER BURDEN?")
    print("=" * 92)
    print(f"   burden alone           CV AUC {cv_auc(Xb, y, rng):.3f}")
    print(f"   burden + slow fraction CV AUC {cv_auc(Xbs, y, rng):.3f}")
    print(f"   out-of-bag increment {inc:+.3f} [{l1:+.3f},{h1:+.3f}] ({k1} reps)   "
          f"{'ADDS' if l1 > 0 else 'does not reach significance'}")
    cl, ch = boot_coef(Xbs, y, 2, rng)
    print(f"   slow-fraction coefficient adjusted for burden: {logit_fit(Xbs, y)[2]:+.2f} [{cl:+.2f},{ch:+.2f}]")

    print("\n" + "=" * 92)
    print("B3  DOES IT ADD OVER BURDEN **AND** THE INTRA-BURST MEASURE?  (the decisive arm)")
    print("=" * 92)
    tri = [p for p in both if p in morph]
    m = len(tri)
    print(f"   patients with background AND intra-burst measures: {m:,}")
    if m >= 150:
        yy = np.array([coh[p] for p in tri])
        b2 = np.array([bg[p]["burden"] for p in tri])
        s2 = np.array([bg[p]["slow"] for p in tri])
        a2 = np.array([morph[p] for p in tri])
        o2 = np.ones(m)
        Xa = np.column_stack([o2, b2, a2])            # burden + intra-burst
        Xc = np.column_stack([o2, b2, a2, s2])        # + background slow
        i2, l2, h2, k2 = oob_increment(Xa, Xc, yy, rng)
        print(f"   burden + intra-burst 8-30 Hz            CV AUC {cv_auc(Xa, yy, rng):.3f}")
        print(f"   + whole-record slow fraction            CV AUC {cv_auc(Xc, yy, rng):.3f}")
        print(f"   out-of-bag increment {i2:+.3f} [{l2:+.3f},{h2:+.3f}] ({k2} reps)")
        cl2, ch2 = boot_coef(Xc, yy, 3, rng)
        print(f"   slow-fraction coefficient, adjusted for BOTH: {logit_fit(Xc, yy)[3]:+.2f} "
              f"[{cl2:+.2f},{ch2:+.2f}]")
        print(f"   B3 {'CONFIRMED -- the background is the better measurement' if cl2 * ch2 > 0 else 'FALSIFIED -- adds nothing beyond intra-burst content'}")
        # and the reverse: does intra-burst still add over the background?
        Xd = np.column_stack([o2, b2, s2])
        i3, l3, h3, _ = oob_increment(Xd, Xc, yy, rng)
        print(f"\n   REVERSE TEST -- does intra-burst content still add over burden + background?")
        print(f"   increment {i3:+.3f} [{l3:+.3f},{h3:+.3f}]   "
              f"{'yes, both matter' if l3 > 0 else 'NO -- the background subsumes it'}")
    else:
        print("   too few with both")

    # ---- B4: coverage ----------------------------------------------------------------------------
    print("\n" + "=" * 92)
    print("B4  COVERAGE -- does it work on the patients morphology cannot see?")
    print("=" * 92)
    nomorph = [p for p in both if p not in morph]
    print(f"   background measurable but morphology NOT: {len(nomorph):,} patients")
    if len(nomorph) >= 40:
        yn = np.array([coh[p] for p in nomorph])
        sn = np.array([bg[p]["slow"] for p in nomorph])
        bn = np.array([bg[p]["burden"] for p in nomorph])
        print(f"   their poor-outcome rate {100*yn.mean():.1f}%   median burden {np.median(bn):.3f}")
        if 0 < yn.sum() < len(yn):
            print(f"   slow fraction among them: good {sn[yn==0].mean():.3f}  poor {sn[yn==1].mean():.3f}")
            print(f"   AUC of slow fraction alone in this subgroup: {auc(yn, -sn):.3f}")
            print("   These are the sickest patients in the cohort and the morphology channel is structurally")
            print("   blind to them. A background measure that discriminates here covers ground morphology")
            print("   cannot, which is the practical argument for preferring it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
