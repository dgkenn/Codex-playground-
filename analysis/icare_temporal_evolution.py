#!/usr/bin/env python3
"""Does the TREND within a recording carry outcome information the level does not?

WHY THIS IS THE LEADING CANDIDATE. The clinician's "generalized slowing" flag carries -0.752 [-1.075, -0.434]
beyond suppression burden and our intra-burst 8-30 Hz measure (R358-R360). Four explanations were named. Two
are now eliminated -- the whole-record background spectrum (B3) and spatial topography (T3) -- and both failed
the same way, which is now catalogue rule 28: a measurement taken in a different *place* is not thereby
measuring a different *thing*. Reactivity is unavailable in this schema. That leaves temporal evolution and
waveform shape, and these differ in KIND rather than in location, which is a positive reason to rank them
above what came before rather than merely the reason they are left.

Every feature this project has computed collapses a recording to a single number. **A human reads a trend.**

------------------------------------------------------------------------------------------------------------
REGISTERED, before the data was looked at.

  E1  DIRECTION. Burden that RISES across the recording marks poor outcome; burden that FALLS marks recovery.
      So the later-minus-earlier difference is HIGHER in poor outcome.

  E2  DECISIVE, and it is a sign test rather than a magnitude test. Decompose burden into two orthogonal
      pieces -- the MEAN across thirds, and the DIFFERENCE (last third minus first third) -- and ask whether
      the difference term carries outcome information adjusted for the mean.
      FALSIFIED IF the difference term's coefficient does not exclude zero, or excludes zero with the WRONG
      sign.

      Why the sign is the whole test, per catalogue rule 12: two noisy measurements of a CONSTANT level
      average to a better estimate than one, so a decomposition can gain predictive accuracy with no trend
      information whatever. Noise cannot, however, produce a correctly-SIGNED non-zero coefficient on the
      difference. Reporting an increment without the sign would not distinguish the two.

  E3  INCREMENT. Out-of-bag AUC increment for adding the trend to the mean. Reported for completeness and
      NOT treated as decisive -- E2's sign is the test.

------------------------------------------------------------------------------------------------------------
THE TIME AXIS HAS TO BE INTACT, and here that is load-bearing rather than hygiene. For a burden -- an average
over frames -- it does not matter that the extraction mask glued frames together across dropouts. For a TREND
it matters completely: a recording missing its middle 1,817 s has a first and last third that are not what
they claim to be. So this analysis is restricted to the interior-gap-filtered set from
`analysis/icare_seq_exclusions.py`. That exclusion is OUTCOME-RELATED (75.3 % poor among excluded versus
61.2 % kept, -14.1 pp [-24.6, -2.9]), so every estimate here is conditioned on it, and the unfiltered
sensitivity run is reported alongside rather than hidden.

WHAT THIS CANNOT DO. One recording of about an hour at roughly hour 24 after arrest. The trend a clinician
actually reads runs over days. A null here rules out the WITHIN-HOUR trend, not temporal evolution as such --
and that distinction is stated in the result rather than discovered afterwards.
"""
import csv, os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from icare_morph_replication import logit_fit, auc, cv_auc, oob_increment

SEQ = os.environ.get("ICARE_SEQ_OUT", "/tmp/eeg_probe/icare_suppseq.csv")
KEEP = os.environ.get("ICARE_KEEP", "/tmp/eeg_probe/icare_seq_keep.csv")
COHORT = os.environ.get("ICARE_COHORT", "/tmp/eeg_probe/icare_cohort.csv")
MORPH = os.environ.get("ICARE_MORPH_OUT", "/tmp/eeg_probe/icare_morph2.csv")
BG = os.environ.get("ICARE_BG_OUT", "/tmp/eeg_probe/icare_background.csv")
NFRAMES = 10
MIN_BINS = int(os.environ.get("MIN_BINS", "600"))     # 10 minutes, so a third is at least 200 s
NBOOT = int(os.environ.get("NBOOT", "800"))


def boot_coef(X, y, col, rng, reps):
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


def diff_ci(x, y, rng, reps):
    n = len(y); bs = []
    for _ in range(reps):
        i = rng.integers(0, n, n)
        a0, a1 = x[i][y[i] == 0], x[i][y[i] == 1]
        if len(a0) > 10 and len(a1) > 10:
            bs.append(a1.mean() - a0.mean())      # poor minus good, matching E1's direction
    if len(bs) < 50:
        return float("nan"), float("nan")
    return tuple(np.percentile(bs, [2.5, 97.5]))


def load():
    coh = {}
    for r in csv.DictReader(open(COHORT)):
        pid = (r.get("pid") or "").strip()
        try:
            c = float(r.get("cpc"))
        except (TypeError, ValueError):
            continue
        if pid and c == c:
            coh[pid] = 1.0 if c >= 3 else 0.0

    keep = None
    if KEEP != "none":
        assert os.path.exists(KEEP), f"{KEEP} missing -- run analysis/icare_seq_exclusions.py"
        keep = {r["pid"].strip() for r in csv.DictReader(open(KEEP))}
        assert keep, f"{KEEP} is empty"

    rows, excl = [], 0
    for r in csv.DictReader(open(SEQ)):
        pid = (r.get("pid") or "").strip()
        c = (r.get("counts_per_second") or "").split()
        if pid not in coh or len(c) < MIN_BINS:
            continue
        if keep is not None and pid not in keep:
            excl += 1
            continue
        try:
            v = np.array([int(x) for x in c], float) / NFRAMES
        except ValueError:
            continue
        k = len(v) // 3
        rows.append(dict(pid=pid, y=coh[pid], t1=float(v[:k].mean()),
                         t2=float(v[k:2 * k].mean()), t3=float(v[2 * k:3 * k].mean()),
                         overall=float(v.mean()), nbins=len(v)))
    return rows, excl, keep is not None


def main():
    rng = np.random.default_rng(20260727)
    rows, excl, filtered = load()
    assert rows, "no recording survived the joins -- check SEQ, COHORT and the keep-list"
    n = len(rows)
    y = np.array([r["y"] for r in rows])
    t1 = np.array([r["t1"] for r in rows])
    t3 = np.array([r["t3"] for r in rows])
    mean3 = np.array([(r["t1"] + r["t2"] + r["t3"]) / 3.0 for r in rows])
    delta = t3 - t1

    print(f"recordings: {n:,}   interior-gap filter {'ON' if filtered else 'OFF (sensitivity run)'}"
          f"   {excl:,} excluded")
    print(f"   poor outcome {100*y.mean():.1f}%   median length {np.median([r['nbins'] for r in rows]):.0f} s")
    print(f"   mean burden {mean3.mean():.3f}   mean within-record change (last third - first third) "
          f"{delta.mean():+.4f}")
    # sanity: the decomposition must be faithful to the raw burden
    assert abs(float(np.corrcoef(mean3, [r["overall"] for r in rows])[0, 1]) - 1.0) < 0.02, \
        "the three-thirds mean does not track the whole-record burden -- the split is wrong"

    # ---- E1 ---------------------------------------------------------------------------------------
    print("\n" + "=" * 96)
    print("E1  DOES BURDEN RISE ACROSS THE RECORDING IN POOR OUTCOME?")
    print("=" * 96)
    d = delta[y == 1].mean() - delta[y == 0].mean()
    lo, hi = diff_ci(delta, y, rng, NBOOT)
    print(f"   change over the recording:  good {delta[y==0].mean():+.4f}   poor {delta[y==1].mean():+.4f}")
    print(f"   difference (poor - good) {d:+.4f} [{lo:+.4f},{hi:+.4f}]   "
          f"{'CONFIRMED' if lo > 0 else ('REVERSED -- burden rises in GOOD outcome' if hi < 0 else 'null')}")
    a = auc(y, delta)
    print(f"   AUC of the trend alone: {max(a, 1-a):.3f}"
          f"   (burden level alone: {max(auc(y, mean3), 1-auc(y, mean3)):.3f})")

    # ---- E2: the decisive sign test ----------------------------------------------------------------
    print("\n" + "=" * 96)
    print("E2  DECISIVE -- SIGN OF THE TREND TERM, ADJUSTED FOR THE LEVEL")
    print("=" * 96)
    one = np.ones(n)
    Xm = np.column_stack([one, mean3])
    Xmd = np.column_stack([one, mean3, delta])
    b = logit_fit(Xmd, y)
    cl, ch = boot_coef(Xmd, y, 2, rng, NBOOT)
    print(f"   mean-burden coefficient   {b[1]:+.3f}")
    print(f"   trend coefficient         {b[2]:+.3f} [{cl:+.3f},{ch:+.3f}]")
    if cl == cl and cl * ch > 0:
        ok = cl > 0
        print(f"   E2 {'CONFIRMED -- correctly signed and excludes zero' if ok else 'REVERSED -- excludes zero with the WRONG sign'}")
        print("   A correctly-signed non-zero coefficient cannot be produced by averaging away noise, which is")
        print("   why the sign and not the increment is the test (catalogue rule 12).")
    else:
        print("   E2 FALSIFIED -- the trend term does not exclude zero. Within-hour temporal evolution")
        print("   carries no outcome information beyond the level. This does NOT rule out evolution over")
        print("   days, which is the trend a clinician actually reads and which one hour cannot show.")

    # ---- E3 ---------------------------------------------------------------------------------------
    print("\n" + "=" * 96)
    print("E3  INCREMENT (reported, not decisive)")
    print("=" * 96)
    inc, l3, h3, k3 = oob_increment(Xm, Xmd, y, rng)
    print(f"   burden level alone     CV AUC {cv_auc(Xm, y, rng):.3f}")
    print(f"   + within-record trend  CV AUC {cv_auc(Xmd, y, rng):.3f}")
    print(f"   out-of-bag increment {inc:+.3f} [{l3:+.3f},{h3:+.3f}] ({k3} reps)")

    # ---- does it survive the measures already in hand? ---------------------------------------------
    morph, bg = {}, {}
    for r in csv.DictReader(open(MORPH)):
        try:
            morph[r["pid"].strip()] = float(r["alpha_beta"])
        except (KeyError, TypeError, ValueError):
            continue
    for r in csv.DictReader(open(BG)):
        try:
            bg[r["pid"].strip()] = float(r["w_slow_frac"])
        except (KeyError, TypeError, ValueError):
            continue
    tri = [i for i, r in enumerate(rows) if r["pid"] in morph and r["pid"] in bg]
    print("\n" + "=" * 96)
    print("DOES THE TREND SURVIVE THE MEASURES WE ALREADY HAVE?")
    print("=" * 96)
    print(f"   patients with trend + background + intra-burst: {len(tri):,}")
    if len(tri) >= 150:
        idx = np.array(tri)
        yy = y[idx]; o = np.ones(len(idx))
        Xa = np.column_stack([o, mean3[idx], np.array([bg[rows[i]['pid']] for i in idx]),
                              np.array([morph[rows[i]['pid']] for i in idx])])
        Xb = np.column_stack([Xa, delta[idx]])
        i2, l4, h4, _ = oob_increment(Xa, Xb, yy, rng)
        c2l, c2h = boot_coef(Xb, yy, 4, rng, NBOOT)
        print(f"   trend coefficient adjusted for burden + background + intra-burst: "
              f"{logit_fit(Xb, yy)[4]:+.3f} [{c2l:+.3f},{c2h:+.3f}]")
        print(f"   out-of-bag increment {i2:+.3f} [{l4:+.3f},{h4:+.3f}]")
        print(f"   {'The trend is NOT redundant with what we already measure.' if c2l == c2l and c2l * c2h > 0 else 'The trend adds nothing beyond the measures already in hand.'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
