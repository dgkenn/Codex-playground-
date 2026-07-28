#!/usr/bin/env python3
"""If the guidelines manufacture the association, the VISIBLE findings should collapse past the withdrawal
window and the INVISIBLE one should not. Do they?

THE INTERPRETIVE PROBLEM THIS ARBITRATES. R404–R406 found that five of six ACNS findings behave differently
by aetiology, with the guideline's flagship pattern — burst suppression — predicting death after anoxia
(+0.47 [+0.29, +0.66]) and carrying essentially nothing otherwise (+0.05 [−0.06, +0.16]). Two readings, and
the analysis so far cannot separate them:

  (A) BIOLOGY. The same EEG pattern really does carry different prognostic information depending on why the
      patient is comatose.
  (B) BEHAVIOUR. These are the flags clinicians read, and the guidelines instruct action on burst suppression
      after cardiac arrest and nowhere else — so guideline-driven withdrawal manufactures exactly this
      pattern.

**The two make different predictions about WHEN the deaths occur, and that is testable.** Withdrawal of care
is concentrated in the first days. If (B) is doing the work, the visible findings' aetiology-dependence should
be **carried by early deaths and collapse once those are excluded**. If (A) is doing the work, the dependence
should persist among patients who survived the window.

**The invisible measure is the control, and it is what makes this interpretable.** Intra-burst 8–30 Hz content
appears in no report and no clinician reads it, so its aetiology-dependence cannot be produced by (B) at all.
It therefore provides the attenuation a purely biological predictor shows in this cohort — the baseline
against which the visible findings must be judged.

------------------------------------------------------------------------------------------------------------
REGISTERED, before the data was looked at.

  X1  For every predictor — the five visible flags and the invisible measure — estimate the aetiology
      interaction twice on identical code: in the full cohort, and restricted to patients ALIVE AT DAY 3.
      Report the retained fraction.

  X2  DECISIVE. The visible findings attenuate MORE than the invisible measure.
      CONFIRMED IF the visible flags' interactions shrink proportionally more than the invisible one's.
      FALSIFIED IF they attenuate similarly — which would mean the landmark is removing signal from all
      predictors alike (power, or genuine early-weighted biology) and provides no evidence for (B).

  X3  HONEST ACCOUNTING. R403 already showed the invisible measure's own anoxic arm attenuates past the
      landmark. So the invisible measure is NOT a zero-attenuation reference; the comparison is relative, and
      if everything attenuates by a similar factor this test returns nothing. That possibility is stated here
      rather than discovered afterwards.

WHAT A POSITIVE MEANS. Evidence that part of the visible findings' aetiology-dependence is guideline-driven
rather than biological — which would be a claim about the literature, not just about this cohort.
WHAT IT CANNOT MEAN. Proof. Withdrawal is unmeasured here; N14 records four failed attempts to build it.
"""
import csv, glob, io, os, sys
from collections import defaultdict
from datetime import datetime

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from icare_morph_replication import logit_fit
from heedb_bs_ascertainment import AETIOLOGY, norm

AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
OMOP_OLD = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
OMOP_Q = os.environ.get("OMOP_QUANT", "/tmp/eeg_probe/heedb_omop_quant")
MORPH = os.environ.get("HEEDB_MORPH", "/tmp/eeg_probe/heedb_burst_morph.s*.csv")
NBOOT = int(os.environ.get("NBOOT", "1500"))
FLAGS = ["bs", "gpd", "lpd", "seizure", "gen slowing", "foc slowing"]


def dt(s):
    s = (s or "").strip()
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, f)
        except ValueError:
            continue
    return None


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


def main():
    rng = np.random.default_rng(20260727)
    import boto3
    from botocore.config import Config
    s3 = boto3.client("s3", region_name="us-east-1",
                      config=Config(s3={"payload_signing_enabled": False}))
    find, when = defaultdict(dict), {}
    for st in ("S0001", "S0002"):
        txt = s3.get_object(Bucket=AP,
                            Key=f"EEG/HEEDB_Metadata/{st}_EEG__reports_findings.csv"
                            )["Body"].read().decode("utf-8", "replace")
        for r in csv.DictReader(io.StringIO(txt)):
            p = (r.get("BDSPPatientID") or "").strip()
            if not p.isdigit():
                continue
            p = int(p)
            for f in FLAGS:
                find[p][f] = find[p].get(f, False) or (
                    (r.get(f) or "").strip() not in ("", "None", "nan"))
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
    src = f"{OMOP_Q}/condition_occurrence.csv"
    assert os.path.exists(src), f"{src} missing"
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
    for p in anox:
        if p not in when or p not in find:
            continue
        d = death.get(p)
        days = (d - when[p]).days if d is not None else None
        if days is not None and days < -1:
            continue
        rows.append((p, days, 1.0 if anox[p] else 0.0, ab.get(p)))
    y = np.array([0.0 if r[1] is None else (1.0 if r[1] <= 30 else 0.0) for r in rows])
    ax = np.array([r[2] for r in rows])
    alive3 = np.array([(r[1] is None) or (r[1] > 3) for r in rows])
    has_ab = np.array([r[3] is not None for r in rows])
    abv = np.array([0.0 if r[3] is None else r[3] for r in rows])
    n = len(rows)
    print(f"cohort {n:,}   30-day death {100*y.mean():.1f}%   anoxic {100*ax.mean():.1f}%")
    print(f"   alive at day 3: {int(alive3.sum()):,} ({100*(1-alive3.mean()):.1f}% died inside the window)")
    print(f"   with the invisible measure: {int(has_ab.sum()):,}")

    def inter(v, mask, label):
        m = mask
        k = int(m.sum())
        if k < 200 or not (0 < y[m].sum() < k):
            return None
        X = np.column_stack([np.ones(k), ax[m], v[m], v[m] * ax[m]])
        c = logit_fit(X, y[m]); lo, hi = boot_coef(X, y[m], 3, rng, NBOOT)
        return c[3], lo, hi, k

    print("\n" + "=" * 104)
    print("X1 / X2  AETIOLOGY INTERACTION: FULL COHORT versus ALIVE AT DAY 3")
    print("=" * 104)
    print(f"{'predictor':>22} {'vis?':>5} {'full cohort':>24} {'alive at day 3':>24} {'retained':>10}")
    print("-" * 104)
    ret = {}
    everyone = np.ones(n, bool)
    for f in FLAGS:
        v = np.array([1.0 if find[r[0]][f] else 0.0 for r in rows])
        a0 = inter(v, everyone, f); a1 = inter(v, alive3, f)
        if not (a0 and a1) or abs(a0[0]) < 1e-9:
            continue
        frac = a1[0] / a0[0]
        ret[f] = frac
        print(f"{f:>22} {'YES':>5} {f'{a0[0]:+.2f} [{a0[1]:+.2f},{a0[2]:+.2f}]':>24} "
              f"{f'{a1[0]:+.2f} [{a1[1]:+.2f},{a1[2]:+.2f}]':>24} {100*frac:>9.0f}%")
    # invisible measure, on the subset that has it, both windows
    b0 = inter(abv, has_ab, "intra-burst")
    b1 = inter(abv, has_ab & alive3, "intra-burst")
    if b0 and b1 and abs(b0[0]) > 1e-9:
        frac = b1[0] / b0[0]
        ret["intra-burst 8-30 Hz"] = frac
        print(f"{'intra-burst 8-30 Hz':>22} {'no':>5} {f'{b0[0]:+.2f} [{b0[1]:+.2f},{b0[2]:+.2f}]':>24} "
              f"{f'{b1[0]:+.2f} [{b1[1]:+.2f},{b1[2]:+.2f}]':>24} {100*frac:>9.0f}%")

    print("\n   'retained' is the day-3 interaction as a fraction of the full-cohort interaction. A predictor")
    print("   whose aetiology-dependence is manufactured by early withdrawal should retain LITTLE of it.")

    print("\n" + "=" * 104)
    print("VERDICT")
    print("=" * 104)
    vis = [ret[f] for f in FLAGS if f in ret]
    inv = ret.get("intra-burst 8-30 Hz")
    if vis and inv is not None:
        print(f"   visible flags retained: {', '.join(f'{100*x:.0f}%' for x in vis)}   "
              f"(median {100*np.median(vis):.0f}%)")
        print(f"   invisible measure retained: {100*inv:.0f}%")
        if np.median(vis) < inv - 0.15:
            print("   X2 CONFIRMED — the visible findings lose more of their aetiology-dependence past the")
            print("   withdrawal window than the invisible one does. Consistent with part of the visible")
            print("   effect being guideline-driven rather than biological.")
        elif abs(np.median(vis) - inv) <= 0.15:
            print("   X2 FALSIFIED — visible and invisible attenuate similarly, so the landmark removes signal")
            print("   from all predictors alike and this test provides NO evidence for the behavioural")
            print("   explanation. That was the pre-registered null and it is what the data show.")
        else:
            print("   X2 REVERSED — the visible findings retain MORE than the invisible one, which the")
            print("   behavioural account does not predict.")
    print("\n   Withdrawal is unmeasured (N14). This is an indirect argument from timing, not proof.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
