#!/usr/bin/env python3
"""Is R360's residual real, or is it the part of burden a LINEAR adjustment fails to remove?

THE FINDING THAT PROMPTED THIS, and it arrived sideways. Trying to validate the report-text
"generalized slowing" flag against MORGOTH 1.0's expert GENSLOWING annotations, the validation failed for
reasons of its own (see `heedb_flag_vs_expert.py`) -- but the diagnostics on the way showed something nobody
had looked at: **the flag's positivity rate collapses as suppression burden rises.**

    burden <1 %    92.7 % flagged        (n = 2,535)
    burden 1-10 %  92.9 %                (n =   874)
    burden 10-50 % 84.1 %                (n =   851)
    burden >50 %   56.1 %                (n =   553)

A reader looking at a near-suppressed record calls it *suppressed*, not *slow*. So "flag absent" does not mean
"no slow activity" -- at high burden it substantially means "so suppressed there is nothing to call slow".

WHY THAT THREATENS R360. R360 is the largest open constraint in the project: the flag carries
**-0.752 [-1.075, -0.434]** for outcome after adjusting for burden and for our intra-burst 8-30 Hz measure.
Three experiments have since failed to explain it (background spectrum B3, topography T3, temporal evolution
R378). All of them assumed the residual is signal. But that adjustment for burden was **linear in burden**, and
the relationship above is anything but linear -- flat to 10 %, then falling off a cliff. **A linear term cannot
absorb a step, so whatever burden-related information the flag carries in its non-linear part survives the
adjustment and appears as a residual.** That is a mechanism for the residual that requires no biology at all.

This is catalogue rule 13's neighbour: not conditioning on a collider, but conditioning with the wrong
functional form, which leaves exactly the structure it was meant to remove.

REGISTERED, before running:
  N1  Replicate R360 as specified -- flag adjusted for LINEAR burden and intra-burst content -- to confirm the
      residual reproduces in this cohort at all. If it does not, nothing below means anything.
  N2  DECISIVE. Re-fit with a FLEXIBLE burden adjustment (quintile indicators, which can represent the step
      shape above without assuming it). If the flag coefficient collapses toward zero, the residual was the
      functional form. If it survives largely intact, the linear-adjustment explanation is dead and the
      residual is more robust than it was before this test.
  N3  Report the flag coefficient under both, and the burden-only models' fit, so the reader can see how much
      of the change is the adjustment rather than the flag.

WHICHEVER WAY IT COMES OUT IT IS INFORMATIVE, which is the point of running it. A collapse retires a
three-experiment mechanism hunt built on an artefact. Survival makes the residual considerably harder to
dismiss, because the most obvious statistical explanation has been excluded.
"""
import csv, io, os, sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from icare_morph_replication import logit_fit, auc, cv_auc

AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
BURDEN = os.environ.get("HEEDB_BURDEN", "/tmp/eeg_probe/heedb_bs_burden_win.s0.csv")
MORPH = os.environ.get("HEEDB_MORPH", "/tmp/eeg_probe/heedb_burst_morph.s0.csv")
NBOOT = int(os.environ.get("NBOOT", "2000"))


def dt(s):
    from datetime import datetime
    s = (s or "").strip()
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
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


def median_by_patient(path, col):
    d = defaultdict(list)
    if not os.path.exists(path):
        return {}
    for r in csv.DictReader(open(path)):
        p = (r.get("patient") or "").strip()
        try:
            v = float(r[col])
        except (KeyError, TypeError, ValueError):
            continue
        if p.isdigit() and v == v:
            d[int(p)].append(v)
    return {p: float(np.median(v)) for p, v in d.items()}


def main():
    rng = np.random.default_rng(20260727)
    import boto3
    from botocore.config import Config
    s3 = boto3.client("s3", region_name="us-east-1",
                      config=Config(s3={"payload_signing_enabled": False}))

    flag, when = {}, {}
    for st in ("S0001", "S0002"):
        txt = s3.get_object(Bucket=AP,
                            Key=f"EEG/HEEDB_Metadata/{st}_EEG__reports_findings.csv"
                            )["Body"].read().decode("utf-8", "replace")
        rd = csv.DictReader(io.StringIO(txt))
        assert "gen slowing" in (rd.fieldnames or []), "'gen slowing' column missing"
        for r in rd:
            p = (r.get("BDSPPatientID") or "").strip()
            if not p.isdigit():
                continue
            p = int(p)
            v = (r.get("gen slowing") or "").strip() not in ("", "None", "nan")
            flag[p] = flag.get(p, False) or v
            t = dt(r.get("EndTime(EEG)") or r.get("StartTime(EEG)") or "")
            if t is not None and (p not in when or t < when[p]):
                when[p] = t

    death = {}
    with open(f"{OMOP}/death.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                death[int(r["person_id"])] = dt(r.get("death_datetime"))
            except (KeyError, TypeError, ValueError):
                pass

    burden = median_by_patient(BURDEN, "burden")
    ab = median_by_patient(MORPH, "alpha_beta")
    assert burden and ab, "burden or morphology table empty -- the join cannot be tested"

    ids = [p for p in burden if p in flag and p in when and p in death and p in ab]
    n = len(ids)
    print(f"cohort with flag + burden + intra-burst + ascertained death: {n:,}")
    assert n >= 200, f"only {n} patients -- too few, and an empty join is not a result"

    y, f, b, a = [], [], [], []
    for p in ids:
        d = death[p]
        if d is None:
            continue
        days = (d - when[p]).days
        if days < -1:
            continue
        y.append(1.0 if days <= 30 else 0.0)
        f.append(1.0 if flag[p] else 0.0)
        b.append(burden[p]); a.append(ab[p])
    y = np.array(y); f = np.array(f); b = np.array(b); a = np.array(a)
    n = len(y)
    print(f"   analysable: {n:,}   30-day death {100*y.mean():.1f}%   flag positive {100*f.mean():.1f}%")

    print("\n" + "=" * 96)
    print("THE SHAPE THAT PROMPTED THIS -- flag positivity by burden")
    print("=" * 96)
    edges = [0, .01, .05, .10, .25, .50, 1.01]
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (b >= lo) & (b < hi)
        if m.sum() > 20:
            print(f"   burden {lo:>5.2f}-{hi:<5.2f}  n={int(m.sum()):>5}  flag positive {100*f[m].mean():5.1f}%"
                  f"   30-day death {100*y[m].mean():5.1f}%")

    one = np.ones(n)
    print("\n" + "=" * 96)
    print("N1  R360 AS SPECIFIED -- flag adjusted for LINEAR burden and intra-burst content")
    print("=" * 96)
    Xlin = np.column_stack([one, b, a, f])
    blin = logit_fit(Xlin, y)
    lo1, hi1 = boot_coef(Xlin, y, 3, rng, NBOOT)
    print(f"   flag coefficient {blin[3]:+.3f} [{lo1:+.3f},{hi1:+.3f}]   "
          f"(burden {blin[1]:+.3f}, intra-burst {blin[2]:+.3f})")
    reproduced = lo1 == lo1 and lo1 * hi1 > 0
    print(f"   {'residual reproduces' if reproduced else 'residual does NOT reproduce in this cohort'}")
    if not reproduced:
        print("\n   *** N1 HAS FAILED ITS GATE. R360 was estimated on a different and larger cohort")
        print(f"   (n = 818); this join yields n = {n:,} and additionally conditions on an ASCERTAINED DEATH")
        print("   record, which this project has already shown is differentially ascertained by aetiology.")
        print("   N2 below is therefore reported for completeness and is NOT interpretable: with a linear")
        print("   coefficient whose interval already spans zero, a flexible adjustment cannot distinguish")
        print("   'the residual collapsed' from 'the residual was never present in this subsample'.")

    print("\n" + "=" * 96)
    print("N2  DECISIVE -- the same model with a FLEXIBLE burden adjustment (quintile indicators)")
    print("=" * 96)
    q = np.quantile(b, [.2, .4, .6, .8])
    D = np.column_stack([(b >= q[i]).astype(float) for i in range(4)])
    print(f"   burden quintile cut-points: {', '.join(f'{x:.4f}' for x in q)}")
    Xflex = np.column_stack([one, D, a, f])
    bflex = logit_fit(Xflex, y)
    lo2, hi2 = boot_coef(Xflex, y, Xflex.shape[1] - 1, rng, NBOOT)
    print(f"   flag coefficient {bflex[-1]:+.3f} [{lo2:+.3f},{hi2:+.3f}]")
    shrink = (1 - abs(bflex[-1]) / abs(blin[3])) * 100 if blin[3] else float("nan")
    print(f"   change from the linear specification: {shrink:+.1f}% in magnitude")
    if not reproduced:
        print("   N2: NO VERDICT -- see the gate failure above. Neither 'survives' nor 'collapses' can be")
        print("   read off a comparison whose baseline never reached significance.")
    elif lo2 * hi2 > 0:
        print("   N2: the residual SURVIVES a flexible burden adjustment. The linear-form explanation is")
        print("   excluded, and the residual is harder to dismiss than it was before this test.")
    else:
        print("   N2: the residual COLLAPSES once burden is modelled flexibly. It was the functional form,")
        print("   not signal -- and the mechanism hunt built on it (B3, T3, R378) was chasing an artefact.")

    print("\n" + "=" * 96)
    print("N3  HOW MUCH OF THIS IS THE ADJUSTMENT RATHER THAN THE FLAG?")
    print("=" * 96)
    for lab, X in (("burden linear only", np.column_stack([one, b])),
                   ("burden quintiles only", np.column_stack([one, D])),
                   ("linear + intra-burst", np.column_stack([one, b, a])),
                   ("quintiles + intra-burst", np.column_stack([one, D, a])),
                   ("linear + intra-burst + flag", Xlin),
                   ("quintiles + intra-burst + flag", Xflex)):
        print(f"   {lab:<32} CV AUC {cv_auc(X, y, rng):.3f}")
    print("\n   If the quintile model alone already matches the linear+flag model, the flag was standing in")
    print("   for the shape of the burden relationship rather than adding information of its own.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
