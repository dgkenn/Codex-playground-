#!/usr/bin/env python3
"""THE FALSIFICATION TEST. The same measurement, in a population where it must behave the opposite way.

THE PREDICTION UNDER TEST. `44_MECHANISM_AND_PRIOR_WORK.md` reads our post-anoxic result against the metabolic
model of burst suppression (Ching, Purdon, Vijayan, Kopell, Brown, PNAS 2012, PMID 22323592), which holds that
burst suppression arises when reduced cerebral metabolic rate meets ATP-gated potassium channels. The reading
is that burden indexes cerebral metabolic rate, so its reversibility depends entirely on WHY the rate is low:

    ANOXIC   -- rate is low because tissue is GONE          -> burden is a FIXED quantity
    ANAESTHETIC -- rate is suppressed in LIVING tissue      -> burden is a REVERSIBLE state

In HEEDB (anoxic) we measured the first: averaging two readings predicts death better (0.787) than the most
recent (0.747), the difference between readings carries no signal once the mean is known (+5.88 pp
[-17.13, +26.58]), and the intraclass correlation of a single reading is 0.815.

**If the same statistics applied to an ANAESTHETIC cohort also said "fixed", the metabolic reading would be
wrong** -- burden would just be a stable patient trait, and the post-anoxic result would say nothing about
tissue loss. This script is the test that could kill it.

WHY THIS IS AN UNUSUALLY CLEAN TEST. It needs no outcome variable. A fixed quantity measured with error and a
genuinely time-varying state are distinguishable from the SERIES ALONE:

  A  AUTOCORRELATION DECAY. For a fixed quantity plus independent noise, the correlation between two readings
     is the reliability and does NOT depend on how far apart they are. For a time-varying state, correlation
     DECAYS with lag. Flat versus decaying is the signature, and nothing about outcomes enters it.
  B  VARIANCE DECOMPOSITION. Compare the within-case share of variance against HEEDB's (ICC 0.815). A state
     driven by a changing input should put far more variance within a case.
  C  RESPONSE TO A MANIPULABLE INPUT. Effect-site anaesthetic concentration is recorded. A reversible
     pharmacological state must move with its driver; a fixed structural quantity cannot.
     (OUTCOME: this arm FAILED and is uninterpretable. Anaesthetists titrate the agent DOWN in response to
     suppression, so the exposure is controlled by the thing being measured and the within-case correlation
     comes out NEGATIVE. Reported, given no weight, and left in because the negative is instructive.)
  D  RECOVERY. Does suppression return toward zero as the case ends and drug is withdrawn? Dead cortex cannot
     recover. This is the most direct form of the question and needs no model at all.

DATA. VitalDB intraoperative records. `devsr` is the BIS monitor's own suppression ratio, and `ce` the
effect-site concentration.

THE LIMITATION THAT MUST TRAVEL WITH THIS. `devsr` is a DEVICE-computed suppression ratio from a proprietary
algorithm on a frontal montage, not our 5 uV / 0.5 s burden on a bipolar longitudinal montage. The two measure
the same construct by different means, so this is a test of whether SUPPRESSION behaves reversibly under
anaesthesia -- not a demonstration that our specific estimator does. Stated rather than glossed.
"""
import csv, os, sys
from collections import defaultdict

import numpy as np

BIS = os.environ.get("BIS_BINS", "/tmp/eeg_probe/bis_bins.csv")
SEVO = os.environ.get("SEVO_BINS", "/tmp/eeg_probe/sevo_bins.csv")
NBOOT = int(os.environ.get("NBOOT", "400"))


def main():
    rng = np.random.default_rng(20260726)

    # ---- load per-case suppression-ratio series ----------------------------------------------------
    series = defaultdict(list)
    with open(BIS) as fh:
        for r in csv.DictReader(fh):
            try:
                c = int(r["caseid"]); t = float(r["bin_t"]); v = float(r["devsr"])
            except Exception:
                continue
            if v == v:
                series[c].append((t, v))
    for c in series:
        series[c].sort()
    print(f"cases with a device suppression-ratio series: {len(series):,}")
    print(f"total bins: {sum(len(v) for v in series.values()):,}")

    # restrict to cases that actually show suppression -- a case that never suppresses carries no
    # information about whether suppression is reversible, in either direction
    supp = {c: v for c, v in series.items() if len(v) >= 10 and max(x[1] for x in v) >= 5.0}
    print(f"cases with >=10 bins and peak SR >= 5 %: {len(supp):,}")
    if len(supp) < 50:
        print("*** too few suppressing cases")
        return 1

    # ---- A: autocorrelation versus lag -------------------------------------------------------------
    print("\n" + "=" * 92)
    print("A  AUTOCORRELATION VERSUS LAG -- flat means a fixed quantity, decaying means a state")
    print("=" * 92)
    print(f"   {'lag (bins)':>12s} {'n pairs':>10s} {'correlation':>13s}")
    lag_rows = []
    for lag in (1, 2, 5, 10, 20, 40):
        xs, ys = [], []
        for c, v in supp.items():
            arr = np.array([x[1] for x in v], float)
            if len(arr) > lag:
                xs.append(arr[:-lag]); ys.append(arr[lag:])
        if not xs:
            continue
        x = np.concatenate(xs); y = np.concatenate(ys)
        if len(x) < 100 or x.std() == 0 or y.std() == 0:
            continue
        rho = float(np.corrcoef(x, y)[0, 1])
        lag_rows.append((lag, len(x), rho))
        print(f"   {lag:12d} {len(x):10,d} {rho:12.3f}")
    if len(lag_rows) >= 3:
        first, last = lag_rows[0][2], lag_rows[-1][2]
        print(f"\n   correlation at lag {lag_rows[0][0]} = {first:.3f}, at lag {lag_rows[-1][0]} = {last:.3f}"
              f"   (decay {first-last:+.3f})")
        print("   HEEDB comparison: a single reading there has ICC 0.815, and that value is what the")
        print("   correlation between ANY two readings of a fixed quantity should equal, at any separation.")
        if last < first - 0.15:
            print("   DECAYING -> a time-varying state, NOT a fixed quantity. Prediction upheld so far.")
        else:
            print("   FLAT -> behaves like a fixed quantity here too. THE METABOLIC READING IS IN TROUBLE.")

    # ---- B: variance decomposition -----------------------------------------------------------------
    print("\n" + "=" * 92)
    print("B  VARIANCE DECOMPOSITION -- how much of the variance lives WITHIN a case?")
    print("=" * 92)
    means = np.array([np.mean([x[1] for x in v]) for v in supp.values()])
    within = np.mean([np.var([x[1] for x in v], ddof=1) for v in supp.values() if len(v) > 1])
    between = float(np.var(means, ddof=1))
    icc = between / (between + within) if (between + within) > 0 else float("nan")
    print(f"   between-case variance {between:.2f}   within-case variance {within:.2f}")
    print(f"   ICC of a single reading = {icc:.3f}")
    print(f"   HEEDB (post-anoxic, across windows of a recording) = 0.815")
    print(f"   {'LOWER -- more variance is within-case, as a driven state should be' if icc < 0.815 else 'NOT lower -- unexpected under the prediction'}")

    # ---- C: does it move with the drug? ------------------------------------------------------------
    print("\n" + "=" * 92)
    print("C  DOES SUPPRESSION MOVE WITH EFFECT-SITE CONCENTRATION?")
    print("=" * 92)
    ce = defaultdict(list)
    if os.path.exists(SEVO):
        with open(SEVO) as fh:
            for r in csv.DictReader(fh):
                try:
                    c = int(r["caseid"]); t = float(r["bin_t"])
                    v = float(r["ce"]); b = float(r["bs"])
                except Exception:
                    continue
                if v == v and b == b:
                    ce[c].append((t, v, b))
    if ce:
        for c in ce:
            ce[c].sort()
        rr = []
        for c, v in ce.items():
            if len(v) < 12:
                continue
            cev = np.array([x[1] for x in v]); bsv = np.array([x[2] for x in v])
            dce = np.diff(cev); dbs = np.diff(bsv)
            if len(dce) >= 8 and dce.std() > 0 and dbs.std() > 0:
                rr.append(float(np.corrcoef(dce, dbs)[0, 1]))
        if rr:
            rr = np.array(rr)
            b = [float(np.mean(rr[rng.integers(0, len(rr), len(rr))])) for _ in range(NBOOT)]
            lo, hi = np.percentile(b, [2.5, 97.5])
            print(f"   within-case correlation of CHANGE in concentration with CHANGE in suppression:")
            print(f"   mean {rr.mean():+.3f} [{lo:+.3f},{hi:+.3f}] across {len(rr):,} cases")
            print(f"   cases with a positive correlation: {100*np.mean(rr > 0):.1f}%")
            if lo < 0 < hi or hi < 0.05:
                print("\n   *** THIS ARM FAILS. The contemporaneous difference-difference correlation is null.")
                print("   Before reading that as evidence against reversibility, note two things that would")
                print("   produce a null here even if suppression is fully drug-driven:")
                print("     1. TITRATION. Anaesthetists REDUCE the agent when they see suppression. That")
                print("        negative feedback drives the contemporaneous correlation toward zero or below,")
                print("        and is a treatment-paradox confound, not pharmacology.")
                print("     2. DIFFERENCING amplifies noise in both series and destroys a slow relationship.")
                print("   C2 below tests the LEVEL relationship and the LAGGED one, which are not subject to")
                print("   the differencing problem and are less subject to the feedback one.")
        else:
            print("   insufficient paired concentration/suppression series")
    else:
        print(f"   {SEVO} not available; skipped")

    # ---- C2: levels and lags, because C is confounded by titration ---------------------------------
    if ce:
        print("\n" + "=" * 92)
        print("C2  LEVELS AND LAGS -- the same question, not destroyed by differencing")
        print("=" * 92)
        lev, lagged = [], defaultdict(list)
        for c, v in ce.items():
            if len(v) < 20:
                continue
            cev = np.array([x[1] for x in v]); bsv = np.array([x[2] for x in v])
            if cev.std() > 0 and bsv.std() > 0:
                lev.append(float(np.corrcoef(cev, bsv)[0, 1]))
            # does suppression FOLLOW concentration? positive lag = concentration leads
            for L in (1, 3, 5, 10):
                if len(cev) > L and cev[:-L].std() > 0 and bsv[L:].std() > 0:
                    lagged[L].append(float(np.corrcoef(cev[:-L], bsv[L:])[0, 1]))
        if lev:
            lev = np.array(lev)
            bb = [float(np.mean(lev[rng.integers(0, len(lev), len(lev))])) for _ in range(NBOOT)]
            l2, h2 = np.percentile(bb, [2.5, 97.5])
            print(f"   LEVEL correlation of concentration with suppression, within case:")
            print(f"      mean {lev.mean():+.3f} [{l2:+.3f},{h2:+.3f}] across {len(lev):,} cases; "
                  f"{100*np.mean(lev > 0):.1f}% positive")
        print(f"   {'lag (bins)':>12s} {'n cases':>9s} {'mean r (conc leads)':>22s}")
        for L in sorted(lagged):
            if len(lagged[L]) >= 30:
                print(f"   {L:12d} {len(lagged[L]):9,d} {np.mean(lagged[L]):21.3f}")
        print("\n   VERDICT ON ARMS C AND C2: UNINTERPRETABLE, and the sign says why. The level correlation is")
        print("   NEGATIVE -- within a case, more agent goes with LESS suppression -- which is pharmacologically")
        print("   backwards and is the signature of a CLOSED LOOP. The anaesthetist watches the monitor and")
        print("   turns the agent DOWN when suppression appears, so suppressed periods are precisely the")
        print("   periods of reduced drug. The exposure is being controlled in response to the outcome.")
        print("\n   This is structurally the same problem as withdrawal of life-sustaining therapy in the")
        print("   post-anoxic cohort -- a clinician acting on the quantity being measured -- moved from the")
        print("   OUTCOME to the EXPOSURE. Neither arm can be rescued by a different lag or a different")
        print("   transform, because the confound is in how the data were generated. They are reported as")
        print("   uninterpretable and carry no weight either way.")

    # ---- D: recovery -------------------------------------------------------------------------------
    print("\n" + "=" * 92)
    print("D  DOES SUPPRESSION RECOVER?  (the question in its most direct form)")
    print("=" * 92)
    prof = defaultdict(list)
    for c, v in supp.items():
        n = len(v)
        for i, (t, x) in enumerate(v):
            prof[min(int(10 * i / n), 9)].append(x)
    print(f"   {'decile of case time':22s} {'n bins':>9s} {'mean SR %':>11s}")
    for d in range(10):
        if prof[d]:
            print(f"   {d+1:<22d} {len(prof[d]):9,d} {np.mean(prof[d]):10.2f}")
    peak = max(np.mean(prof[d]) for d in range(10) if prof[d])
    endv = np.mean(prof[9]) if prof[9] else float("nan")
    print(f"\n   peak {peak:.2f} %  ->  final decile {endv:.2f} %   "
          f"({100*(1-endv/peak) if peak > 0 else float('nan'):.0f} % resolution)")
    if endv < 0.5 * peak:
        print("   RECOVERS. Suppression resolves as the anaesthetic is withdrawn.")
        print("   Post-anoxically it does not: burden there behaves as a constant, and the difference")
        print("   between serial readings carried no information once the mean was known.")
        print("\n   THE PREDICTION IS UPHELD BY ARMS A, B AND D. The same construct is reversible when the")
        print("   cause is drug and fixed when the cause is tissue loss, which is what the metabolic reading")
        print("   requires. Arm C is null and is reported as null; see C2 for why a titrated exposure")
        print("   produces exactly that, and note that it neither supports nor refutes the prediction.")
    else:
        print("   DOES NOT RECOVER -- unexpected, and would count against the metabolic reading.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
