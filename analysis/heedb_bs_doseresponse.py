#!/usr/bin/env python3
"""Does MEASURED burst-suppression burden reproduce the aetiology interaction that the clinician LABEL showed?

WHY THIS IS THE MOST IMPORTANT REMAINING TEST. The finding in docs/research/39_HEEDB_FINDINGS.md rests on a
binary label written on a report by whichever neurophysiologist read that study. Two weaknesses follow, and both
are listed as limitations there:

  * it is binary, so no dose-response can be tested -- and dose-response is among the strongest observational
    evidence available for a real effect (it is what carried the VitalDB arm of this project);
  * reader heterogeneity is an unmeasured error source, since readers differ in their threshold for calling
    suppression, and a reader who is systematically liberal in post-arrest patients would produce exactly the
    aetiology-dependent pattern the paper reports.

This replaces the label with a quantity measured directly from the raw EDF by a detector calibrated in-
distribution against HEEDB's own expert labels. That detector reproduces out-of-sample on this cohort at
AUC 0.783 [0.769, 0.800] (median burden 0.471 in clinician-positive patients against 0.016 in negatives), so it
is measuring the same thing the readers were, independently of who wrote the report.

If the interaction survives with measured burden, reader heterogeneity is ruled out as its cause and the exposure
becomes graded. If it does not survive, the paper's central claim is in serious trouble and that is reported.

REGISTERED PREDICTIONS, stated before running.
  D1  The burden x aetiology interaction reproduces the SIGN PATTERN of the label-based interaction: anoxic the
      most positive term, sepsis the most negative. (Label-based: anoxic +23.59, status -5.84, metabolic -1.41,
      structural -9.28, sepsis -14.92 pp.)
      FALSIFIED IF anoxic is not the largest positive term, or if the interaction spread's interval covers zero.
  D2  DOSE-RESPONSE within anoxic patients: higher measured burden predicts higher 30-day death. A graded
      relationship is the thing the binary label could not test and is the point of the exercise.
      FALSIFIED IF the anoxic-stratum slope covers zero.

  ATTENUATION IS EXPECTED AND IS NOT A FAILURE. Burden is estimated from four 120 s windows per recording, so it
  carries substantial sampling error against a reader who saw the whole record. Classical measurement error in a
  continuous exposure biases coefficients TOWARD null (regression dilution). The predictions above are therefore
  about SIGN and ORDERING, not about magnitude matching the label-based estimates -- a smaller effect is the
  expected result, and only a null or a reversal falsifies.

DESIGN: ascertainment-immune throughout, matching section 4 of the findings document -- every patient has a
recorded death and the outcome is whether it came within 30 days. Helpers are imported from the validated
modules rather than reimplemented.
"""
import csv, glob, os, sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from heedb_bs_ascertainment import AETIOLOGY, norm, dt
# NOT heedb_bs_ascertainment.eeg_times -- that function returns times ONLY for patients carrying a
# burst-suppression label (it skips reports whose `bs` field is empty), because it was written for the BS
# cohort. Using it here silently restricted this model to BS-positive patients, excluding the BS-negative
# comparison group entirely, and made the burden x aetiology interaction non-comparable to the label-based
# one it is supposed to reproduce. all_eeg_patients() returns every EEG patient with a timestamp.
from heedb_bs_specificity import all_eeg_patients

OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
NBOOT = int(os.environ.get("NBOOT", "2000"))
BURDEN_GLOB = os.environ.get("BURDEN_GLOB", "/tmp/eeg_probe/heedb_bs_burden*.csv")


def load_burden():
    """patient -> MAX burden across that patient's recordings.

    Max, not mean: the clinician label is 'suppression was present on some report', suppression is intermittent,
    and averaging across recordings dilutes presence. This matches how the detector was calibrated.
    """
    b = {}
    for f in sorted(glob.glob(BURDEN_GLOB)):
        try:
            for r in csv.DictReader(open(f)):
                try:
                    p, v = int(r["patient"]), float(r["burden"])
                except Exception:
                    continue
                if v == v:
                    b[p] = max(b.get(p, 0.0), v)
        except FileNotFoundError:
            continue
    return b


def main():
    rng = np.random.default_rng(20260725)
    burden = load_burden()
    print(f"patients with a measured burden: {len(burden)}")
    if len(burden) < 500:
        print("too few measured recordings yet; rerun when quantification has progressed"); return 1

    aet, cond_seen = defaultdict(set), set()
    with open(f"{OMOP}/condition_occurrence.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                p = int(r["person_id"])
            except Exception:
                continue
            cond_seen.add(p)
            c = norm(r.get("condition_source_value"))
            if not c:
                continue
            for lab, pre in AETIOLOGY.items():
                if any(c.startswith(x) for x in pre):
                    aet[p].add(lab)

    death = {}
    with open(f"{OMOP}/death.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                death[int(r["person_id"])] = dt(r.get("death_datetime"))
            except Exception:
                pass

    et, bs_label, _age, _fem = all_eeg_patients()
    keys = list(AETIOLOGY)
    rows = []
    for p in sorted(cond_seen & set(burden)):
        d, t = death.get(p), et.get(p)
        if d is None or t is None:
            continue
        days = (d - t).days
        if days < -1:
            continue
        labs = aet.get(p, set())
        rows.append(dict(d30=1.0 if days <= 30 else 0.0, bur=float(burden[p]),
                         labelled=1.0 if bs_label.get(p) else 0.0,
                         **{k: (1.0 if k in labs else 0.0) for k in keys}))
    n = len(rows)
    print(f"analysable (measured burden + ascertained death + EEG time + condition data): {n}")
    if n < 300:
        print("insufficient"); return 1
    bv = np.array([r["bur"] for r in rows])
    nlab = int(sum(r["labelled"] for r in rows))
    print(f"  clinician BS-labelled in this set: {nlab} ({100*nlab/n:.1f} %); unlabelled: {n-nlab}")
    print(f"  burden distribution: median {np.median(bv):.3f}  IQR "
          f"[{np.percentile(bv,25):.3f},{np.percentile(bv,75):.3f}]  max {bv.max():.3f}")
    if nlab / n > 0.9:
        print("  *** the analysable set is almost entirely BS-labelled -- the BS-negative comparison group is")
        print("      missing, so the interaction below is NOT comparable to the label-based one. Check the")
        print("      EEG-time source: it must cover all EEG patients, not only those carrying a bs label.")

    expo = [k for k in keys if sum(r[k] for r in rows) >= 30]
    y = np.asarray([r["d30"] for r in rows], float)

    def design(R):
        m = len(R)
        b = np.asarray([r["bur"] for r in R], float)
        cols = [np.ones(m), b]
        for k in expo:
            cols.append(np.asarray([r[k] for r in R], float))
        for k in expo:
            cols.append(b * np.asarray([r[k] for r in R], float))
        return np.column_stack(cols), np.asarray([r["d30"] for r in R], float)

    X, _ = design(rows)
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    i0 = 2 + len(expo)                      # first burden x aetiology interaction column
    int_idx = list(range(i0, i0 + len(expo)))

    print("\n=== burden x aetiology INTERACTION (per unit burden, i.e. 0 -> fully suppressed) ===")
    for j, k in zip(int_idx, expo):
        print(f"   {k:12s} {100*beta[j]:+7.2f} pp")
    obs_spread = float(max(beta[int_idx]) - min(beta[int_idx]))
    order = [k for _, k in sorted(zip(beta[int_idx], expo), reverse=True)]
    print(f"   ordering, most positive first: {order}")
    print(f"   spread {100*obs_spread:.2f} pp")

    bs_spread = []
    for _ in range(NBOOT):
        i = rng.integers(0, n, n)
        try:
            X2, y2 = design([rows[j] for j in i])
            b2 = np.linalg.lstsq(X2, y2, rcond=None)[0]
        except Exception:
            continue
        bs_spread.append(float(max(b2[int_idx]) - min(b2[int_idx])))
    lo, hi = np.percentile(bs_spread, [2.5, 97.5])
    print(f"   interaction spread {100*obs_spread:.2f} pp [{100*lo:.2f},{100*hi:.2f}] "
          f"{'*' if lo > 0 else 'ns'}")
    d1 = (order and order[0] == "anoxic" and lo > 0)
    print(f"   D1 (anoxic largest positive AND spread excludes zero): "
          f"{'CONFIRMED' if d1 else 'FALSIFIED'}")

    # ---- D2: dose-response within the anoxic stratum ----------------------------------------------------
    print("\n=== D2: dose-response WITHIN anoxic patients ===")
    an = [r for r in rows if r["anoxic"] > 0]
    if len(an) < 100:
        print(f"   only {len(an)} anoxic patients with a measured burden; not testable yet"); return 0
    xb = np.asarray([r["bur"] for r in an], float)
    ya = np.asarray([r["d30"] for r in an], float)
    Xa = np.column_stack([np.ones(len(an)), xb])
    ba = np.linalg.lstsq(Xa, ya, rcond=None)[0]
    sl = []
    for _ in range(NBOOT):
        i = rng.integers(0, len(an), len(an))
        try:
            sl.append(float(np.linalg.lstsq(Xa[i], ya[i], rcond=None)[0][1]))
        except Exception:
            continue
    lo2, hi2 = np.percentile(sl, [2.5, 97.5])
    print(f"   n={len(an)}  slope per unit burden {100*ba[1]:+.2f} pp [{100*lo2:+.2f},{100*hi2:+.2f}] "
          f"{'*' if (lo2 > 0 or hi2 < 0) else 'ns'}")
    print(f"   D2 (slope excludes zero and is positive): {'CONFIRMED' if lo2 > 0 else 'FALSIFIED'}")

    # quartile view: a monotone gradient is more convincing than a linear slope
    q = np.percentile(xb, [25, 50, 75])
    print("   by burden quartile (30-day death):")
    for lab, sel in (("Q1 lowest", xb <= q[0]), ("Q2", (xb > q[0]) & (xb <= q[1])),
                     ("Q3", (xb > q[1]) & (xb <= q[2])), ("Q4 highest", xb > q[2])):
        if sel.sum() >= 10:
            print(f"      {lab:11s} n={int(sel.sum()):4d}  {100*ya[sel].mean():5.1f} %")

    print("\n   Measurement error attenuates a continuous exposure toward null (regression dilution), and burden")
    print("   is estimated from four 120 s windows per recording, so a SMALLER effect than the label-based one")
    print("   is expected. Only a null or a reversal falsifies the predictions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
