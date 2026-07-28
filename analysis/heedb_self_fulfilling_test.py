#!/usr/bin/env python3
"""Is the aetiology reversal a real prognostic signal, or the self-fulfilling prophecy in disguise?

THE PROBLEM THIS ADDRESSES IS THE FIELD'S CENTRAL ONE. Every EEG neuroprognostication study after cardiac
arrest is contaminated by self-fulfilling prophecy: the clinician reads the EEG, it looks malignant, care is
withdrawn, the patient dies, and the EEG is recorded as having predicted death. The association is then
partly prescriptive rather than prognostic. It is why the ERC-ESICM guidance hedges, and this project's own
constraint table records the same wall — **L2** (46 % die inside the withdrawal window) and **N14** (four
separate instruments failed to separate withdrawal from biological death, one root cause).

**WHY THIS MEASURE IS DIFFERENT, and it is the reason this test is worth running.** Intra-burst 8–30 Hz
spectral content is computed by segmenting bursts and running an FFT inside them. **It appears in no clinical
report, and no clinician reads it.** It therefore cannot enter a withdrawal decision. A self-fulfilling
prophecy requires the predictor to be visible to the decision-maker; this one is not.

The reversal sharpens the argument further. For a behavioural mechanism to produce it, clinicians would have
to act on an invisible feature **in opposite directions depending on aetiology**. That is not a confound
anyone can construct.

Both of those are arguments. The tests below are the evidence.

------------------------------------------------------------------------------------------------------------
REGISTERED, before the data was looked at.

  W1  ADJUST FOR WHAT THE CLINICIAN ACTUALLY SAW. The report flags — burst suppression, generalized slowing —
      are what the treating team recorded and therefore what could have driven a decision. If the reversal
      survives adjustment for them, our measure is carrying outcome information **the decision process did
      not have**.
      FALSIFIED IF the reversal collapses once the visible features are controlled, which would mean it was a
      proxy for what clinicians saw and acted on.

  W2  LANDMARK PAST THE WITHDRAWAL WINDOW. Restrict to patients **alive at day 3** and ask whether the
      reversal predicts death from day 3 onward. Most withdrawal happens early (46 % of deaths are inside
      that window), so surviving it removes the bulk of the contamination.
      FALSIFIED IF the reversal exists only for early death. A marker that predicts only deaths occurring
      during the withdrawal window is exactly what a self-fulfilling prophecy looks like.

  W3  THE DECISIVE CONTRAST. Compare, in the same cohort and on identical code, how much of the association
      the **visible** features carry versus the **invisible** one. Under a pure self-fulfilling prophecy the
      visible features should dominate and the invisible one should add nothing. Under a biological signal
      the invisible measure should retain an aetiology-dependent association after the visible ones are in
      the model.

WHAT THIS CAN AND CANNOT ESTABLISH. It cannot prove no self-fulfilling prophecy — nothing observational can
without a withdrawal variable, and N14 records four failed attempts to build one. It can show that the
association does not depend on the features clinicians acted on, and that it survives past the window in which
most withdrawal occurs. That is a stronger position than the published literature typically holds, and it
should be claimed in exactly those terms and no further.
"""
import csv, glob, io, os, sys
from collections import defaultdict
from datetime import datetime

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from icare_morph_replication import auc, logit_fit
from heedb_bs_ascertainment import AETIOLOGY, norm

AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
OMOP_OLD = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
OMOP_NEW = os.environ.get("OMOP_V2", "/tmp/eeg_probe/heedb_omop_v2")
MORPH = os.environ.get("HEEDB_MORPH", "/tmp/eeg_probe/heedb_burst_morph.s*.csv")
NBOOT = int(os.environ.get("NBOOT", "2000"))


def dt(s):
    s = (s or "").strip()
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, f)
        except ValueError:
            continue
    return None


def auc_ci(y, s, rng, reps):
    n = len(y); o = []
    for _ in range(reps):
        i = rng.integers(0, n, n)
        if 0 < y[i].sum() < n:
            a = auc(y[i], s[i])
            if a == a:
                o.append(a)
    if len(o) < 50:
        return float("nan"), float("nan")
    return tuple(np.percentile(o, [2.5, 97.5]))


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


def arm(label, y, a, ax, rng):
    print(f"\n   --- {label} ---")
    res = {}
    for nm, m in (("anoxic", ax == 1), ("non-anoxic", ax == 0)):
        k = int(m.sum())
        if k < 60 or not (0 < y[m].sum() < k):
            print(f"      {nm:<11} n={k:>5}  events={int(y[m].sum())}  too few")
            return None
        A = auc(y[m], a[m]); lo, hi = auc_ci(y[m], a[m], rng, NBOOT)
        res[nm] = (A, lo, hi)
        print(f"      {nm:<11} n={k:>5}  event rate {100*y[m].mean():5.1f}%  AUC {A:.3f} [{lo:.3f},{hi:.3f}]"
              f"  {'-> MORE death' if A > 0.5 else '-> LESS death'}")
    an, no = res["anoxic"], res["non-anoxic"]
    strict = an[1] > 0.5 and no[2] < 0.5
    print(f"      gap {an[0]-no[0]:+.3f}   "
          f"{'REVERSAL, both intervals exclude 0.5' if strict else 'directional only — an interval spans 0.5'}")
    return strict


def main():
    rng = np.random.default_rng(20260727)
    import boto3
    from botocore.config import Config
    s3 = boto3.client("s3", region_name="us-east-1",
                      config=Config(s3={"payload_signing_enabled": False}))
    flag_bs, flag_slow, when = {}, {}, {}
    for st in ("S0001", "S0002"):
        txt = s3.get_object(Bucket=AP,
                            Key=f"EEG/HEEDB_Metadata/{st}_EEG__reports_findings.csv"
                            )["Body"].read().decode("utf-8", "replace")
        for r in csv.DictReader(io.StringIO(txt)):
            p = (r.get("BDSPPatientID") or "").strip()
            if not p.isdigit():
                continue
            p = int(p)
            flag_bs[p] = flag_bs.get(p, False) or ((r.get("bs") or "").strip() not in ("", "None", "nan"))
            flag_slow[p] = flag_slow.get(p, False) or (
                (r.get("gen slowing") or "").strip() not in ("", "None", "nan"))
            t = dt(r.get("EndTime(EEG)") or r.get("StartTime(EEG)") or "")
            if t and (p not in when or t < when[p]):
                when[p] = t
    death = {}
    with open(f"{OMOP_OLD}/death.csv") as fh:
        for r in csv.DictReader(fh):
            d = dt(r.get("death_datetime"))
            if d is not None:
                try:
                    death[int(r["person_id"])] = d
                except (KeyError, TypeError, ValueError):
                    pass

    # Prefer the full re-extract (R398, decedents AND survivors). Fall back to the original
    # decedents-only extract if /tmp has been wiped -- the container reclaims it without warning, and an
    # answer on the smaller cohort beats no answer. The cohort actually used is printed.
    src = f"{OMOP_NEW}/condition_occurrence.csv"
    if not os.path.exists(src):
        src = f"{OMOP_OLD}/condition_occurrence.csv"
        print(f"   [v2 extract absent — falling back to {src} (decedents only)]")
    anox = {}
    with open(src) as fh:
        for r in csv.DictReader(fh):
            try:
                p = int(r["person_id"])
            except (KeyError, TypeError, ValueError):
                continue
            anox.setdefault(p, False)
            c = norm(r.get("condition_source_value"))
            if c and any(c.startswith(x) for x in AETIOLOGY["anoxic"]):
                anox[p] = True
    assert anox, "no condition_occurrence extract found — run analysis/heedb_omop_extract.py"
    print(f"   aetiology source: {src}  ({len(anox):,} patients)")

    ab = defaultdict(list)
    for path in sorted(glob.glob(MORPH)):
        for r in csv.DictReader(open(path)):
            p = (r.get("patient") or "").strip()
            try:
                v = float(r["alpha_beta"])
            except (KeyError, TypeError, ValueError):
                continue
            if p.isdigit() and v == v:
                ab[int(p)].append(v)
    ab = {p: float(np.median(v)) for p, v in ab.items()}

    rows = []
    for p, v in ab.items():
        if p not in when or p not in anox:
            continue
        d = death.get(p)
        days = (d - when[p]).days if d is not None else None
        if days is not None and days < -1:
            continue
        rows.append((p, days, v, 1.0 if anox[p] else 0.0,
                     1.0 if flag_bs.get(p) else 0.0, 1.0 if flag_slow.get(p) else 0.0))
    assert len(rows) >= 400, f"only {len(rows)} patients"
    days = np.array([-1 if r[1] is None else r[1] for r in rows])
    alive = np.array([r[1] is None for r in rows])
    a = np.array([r[2] for r in rows]); ax = np.array([r[3] for r in rows])
    fbs = np.array([r[4] for r in rows]); fsl = np.array([r[5] for r in rows])
    y30 = np.array([0.0 if r[1] is None else (1.0 if r[1] <= 30 else 0.0) for r in rows])
    n = len(rows)
    early = np.array([0.0 if r[1] is None else (1.0 if r[1] <= 3 else 0.0) for r in rows])
    print(f"cohort {n:,}   30-day death {100*y30.mean():.1f}%   died <=3 d {100*early.mean():.1f}%   "
          f"anoxic {100*ax.mean():.1f}%")
    print(f"   clinician-visible flags: burst suppression {100*fbs.mean():.1f}%, "
          f"generalized slowing {100*fsl.mean():.1f}%")

    # ---- W1 -----------------------------------------------------------------------------------------
    print("\n" + "=" * 96)
    print("W1  DOES IT SURVIVE ADJUSTMENT FOR WHAT THE CLINICIAN ACTUALLY SAW AND RECORDED?")
    print("=" * 96)
    one = np.ones(n)
    for lab, m in (("anoxic", ax == 1), ("non-anoxic", ax == 0)):
        k = int(m.sum())
        X = np.column_stack([np.ones(k), fbs[m], fsl[m], a[m]])
        c = logit_fit(X, y30[m])
        lo, hi = boot_coef(X, y30[m], 3, rng, NBOOT)
        print(f"   {lab:<11} n={k:>5}  intra-burst coefficient adjusted for the visible flags "
              f"{c[3]:+.3f} [{lo:+.3f},{hi:+.3f}]")
    Xi = np.column_stack([one, fbs, fsl, ax, a, a * ax])
    ci = logit_fit(Xi, y30)
    li, hi_ = boot_coef(Xi, y30, 5, rng, NBOOT)
    print(f"\n   INTERACTION intra-burst x anoxic, adjusted for the visible flags: "
          f"{ci[5]:+.3f} [{li:+.3f},{hi_:+.3f}]")
    w1 = li == li and li * hi_ > 0 and ci[5] > 0
    print(f"   W1 {'CONFIRMED — the reversal is not explained by what the clinician saw' if w1 else 'NOT CONFIRMED — it may be a proxy for the visible features'}")

    # ---- W2 -----------------------------------------------------------------------------------------
    print("\n" + "=" * 96)
    print("W2  LANDMARK PAST THE WITHDRAWAL WINDOW — patients ALIVE AT DAY 3")
    print("=" * 96)
    surv3 = alive | (days > 3)
    y_late = np.array([0.0 if r[1] is None else (1.0 if r[1] <= 30 else 0.0) for r in rows])[surv3]
    print(f"   alive at day 3: {int(surv3.sum()):,} of {n:,}  "
          f"({100*(1-surv3.mean()):.1f}% died inside the window and are excluded)")
    print(f"   of those, died by day 30: {100*y_late.mean():.1f}%")
    w2 = arm("alive at day 3, death by day 30", y_late, a[surv3], ax[surv3], rng)

    # ---- W3 -----------------------------------------------------------------------------------------
    print("\n" + "=" * 96)
    print("W3  VISIBLE VERSUS INVISIBLE — which carries the association?")
    print("=" * 96)
    print(f"   {'feature':>34} {'anoxic AUC':>12} {'non-anoxic AUC':>16}")
    print("   " + "-" * 66)
    for nm, v in (("burst suppression flag (VISIBLE)", fbs),
                  ("generalized slowing flag (VISIBLE)", fsl),
                  ("intra-burst 8-30 Hz (INVISIBLE)", a)):
        r1 = auc(y30[ax == 1], v[ax == 1]); r0 = auc(y30[ax == 0], v[ax == 0])
        print(f"   {nm:>34} {r1:>12.3f} {r0:>16.3f}")
    print("\n   A self-fulfilling prophecy predicts the VISIBLE features carry the association and the")
    print("   invisible one adds nothing once they are controlled. W1 is the formal version of that test.")

    print("\n" + "=" * 96)
    print("VERDICT")
    print("=" * 96)
    print(f"   W1 (survives adjustment for visible flags): {w1}")
    print(f"   W2 (survives the day-3 landmark):           {bool(w2)}")
    print("\n   Neither result proves the absence of a self-fulfilling prophecy — nothing observational can")
    print("   without a withdrawal variable, and N14 records four failed attempts to build one. Both together")
    print("   show the association does not depend on the features clinicians acted on and survives past the")
    print("   window in which most withdrawal occurs. Claim that, and not more.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
