#!/usr/bin/env python3
"""Does the reversal run through EPILEPTOGENICITY? The leading mechanism candidate, with a testable handle.

THE CANDIDATE (C in the 2026-07-29 cadence brainstorm). Fast-spiking inhibitory interneurons are selectively
vulnerable to hypoxia-ischaemia. If that is what separates the aetiologies, then surviving 8-30 Hz activity
means different things in the two groups:

    ANOXIC      interneurons preferentially lost -> residual fast activity is DISINHIBITED, epileptogenic
                cortex. More fast content = worse.
    NON-ANOXIC  inhibition relatively spared -> residual fast activity is PRESERVED cortical function.
                More fast content = better.

That is the only candidate on the list that explains the **sign reversal** directly rather than predicting a
mere weakening, and R413 sharpened it further: the reversal lives in spectral CONTENT and in none of five
other morphology measures from the same bursts. An interneuron account is about what the surviving circuit
does, not about how vigorous the bursts are.

**Why it is testable now, and why this is not a re-slicing of the death analysis.** The findings tables carry
clinician-marked epileptiform features — GPD, LPD and seizure — on every patient. So the candidate can be
tested against a **new outcome** that is not death at all. A mechanism that predicts a second, different
association is worth far more than one that re-explains the first.

**A LITERATURE PREMISE THAT WAS CHECKED FIRST (catalogue rule 21).** "Dead cortex cannot seize" is sound
physiology and false after cardiac arrest — post-anoxic status epilepticus and generalized periodic
discharges are well described and are markers of severe injury. This project already recorded that as a rule
after being burned by the opposite assumption. So the premise here — that badly injured anoxic cortex CAN
generate epileptiform activity — is the established one, not the convenient one.

------------------------------------------------------------------------------------------------------------
REGISTERED, before the data was looked at.

  E0  PRECONDITION (rule 32). Epileptiform findings must VARY in both aetiology arms, and intra-burst content
      must vary in both. Report the prevalences. If an arm is near 0 % or near 100 % epileptiform, the
      interaction is not estimable there and this script must say so instead of reporting a null.

  E1  PRIMARY. Outcome = ANY epileptiform finding (GPD or LPD or seizure). Estimate the
      aetiology x intra-burst-content interaction, adjusted for suppression burden as quintile indicators.
        SUPPORTS C IF the interaction is POSITIVE and excludes zero — content is more strongly tied to
        epileptiform activity in anoxic patients than in non-anoxic ones.
        FAILS IF it includes zero or is negative. Candidate C then loses its only concrete handle in this
        dataset and should be demoted rather than kept alive on plausibility.

  E2  PLACEBO, and it GATES E1 (rule 34). Repeat with **focal slowing** as the outcome — a non-epileptiform
      finding the interneuron account says nothing about. If the same interaction appears there, the
      statistic is tracking "how much abnormality the reader described", not epileptogenicity, and E1 carries
      no weight.

  E3  EXPLORATORY, labelled as such. Within the anoxic arm, is the content->death association weaker among
      patients WITHOUT epileptiform findings? This is a mediation-flavoured question and conditioning on a
      post-exposure variable is exactly what catalogue rule 13 warns about, so it is descriptive only and no
      claim may rest on it.

  E4  THE SHARED-WAVEFORM CAVEAT, quantified rather than waved away. If periodic discharges occur INSIDE
      bursts, then intra-burst 8-30 Hz content and "GPD present" partly measure the same waveforms, which
      would make E1 true trivially. Report the content-epileptiform correlation within each arm.
      **The defence is structural: that overlap exists equally in both arms, so it cannot by itself produce
      an aetiology DIFFERENCE.** E1 tests the difference, not the association.

WHAT A POSITIVE MEANS. A mechanism that predicted a second, independent association and got it — the
strongest evidence this dataset can produce for any mechanistic account.
WHAT IT CANNOT MEAN. Causation, or interneuron loss specifically. Epileptiform activity is a downstream
marker compatible with several accounts; this test discriminates C from "no epileptogenic pathway at all",
not C from every rival.
"""
import csv, glob, io, os, sys
from collections import defaultdict
from datetime import datetime

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.awsenv import sanitize as _aws_sanitize; _aws_sanitize()
from icare_morph_replication import logit_fit

AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
MORPH = os.environ.get("HEEDB_MORPH", "/tmp/eeg_probe/heedb_burst_morph.s*.csv")
NBOOT = int(os.environ.get("NBOOT", "2000"))
EPI = ["gpd", "lpd", "seizure"]
PLACEBO = "foc slowing"
ALLFLAGS = EPI + [PLACEBO]


def dt(s):
    s = (s or "").strip()
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, f)
        except ValueError:
            continue
    return None


def z(a):
    s = a.std()
    return (a - a.mean()) / (s if s > 1e-12 else 1.0)


def quintiles(b):
    e = np.quantile(b, [0.2, 0.4, 0.6, 0.8])
    idx = np.searchsorted(e, b, side="right")
    return np.column_stack([(idx == k).astype(float) for k in range(1, 5)])


def auc(v, y):
    if not (0 < y.sum() < len(y)):
        return float("nan")
    r = np.argsort(np.argsort(v)).astype(float) + 1.0
    n1 = float(y.sum()); n0 = float(len(y) - n1)
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0)


def main():
    rng = np.random.default_rng(20260729)
    import boto3
    from botocore.config import Config
    s3 = boto3.client("s3", region_name="us-east-1",
                      config=Config(s3={"payload_signing_enabled": False}))
    find, when = defaultdict(dict), {}
    for st in ("S0001", "S0002"):
        txt = s3.get_object(Bucket=AP,
                            Key=f"EEG/HEEDB_Metadata/{st}_EEG__reports_findings.csv"
                            )["Body"].read().decode("utf-8", "replace")
        rd = csv.DictReader(io.StringIO(txt))
        for f in ALLFLAGS:
            assert f in (rd.fieldnames or []), f"'{f}' column missing from the findings table"
        for r in rd:
            p = (r.get("BDSPPatientID") or "").strip()
            if not p.isdigit():
                continue
            p = int(p)
            for f in ALLFLAGS:
                find[p][f] = find[p].get(f, False) or (
                    (r.get(f) or "").strip() not in ("", "None", "nan"))
            t = dt(r.get("EndTime(EEG)") or r.get("StartTime(EEG)") or "")
            if t and (p not in when or t < when[p]):
                when[p] = t
    death = {}
    with open(f"{OMOP}/death.csv") as fh:
        for r in csv.DictReader(fh):
            d = dt(r.get("death_datetime"))
            if d is not None:
                try:
                    death[int(r["person_id"])] = d
                except (KeyError, TypeError, ValueError):
                    pass
    from heedb_aetiology_compact import load_anoxic
    anox = load_anoxic()

    acc = {c: defaultdict(list) for c in ("alpha_beta", "burden")}
    for path in sorted(glob.glob(MORPH)):
        for r in csv.DictReader(open(path)):
            p = (r.get("patient") or "").strip()
            if not p.isdigit():
                continue
            for c in acc:
                try:
                    v = float(r[c])
                except (KeyError, TypeError, ValueError):
                    continue
                if v == v:
                    acc[c][int(p)].append(v)
    M = {c: {p: float(np.median(v)) for p, v in d.items()} for c, d in acc.items()}
    assert M["alpha_beta"], "morphology cache empty -- an empty join is not a result"

    rows = []
    for p in M["alpha_beta"]:
        if p not in M["burden"] or p not in anox or p not in when or p not in find:
            continue
        d = death.get(p)
        days = (d - when[p]).days if d is not None else None
        if days is not None and days < -1:
            continue
        rows.append((1.0 if anox[p] else 0.0, M["alpha_beta"][p], M["burden"][p],
                     1.0 if any(find[p][f] for f in EPI) else 0.0,
                     1.0 if find[p][PLACEBO] else 0.0,
                     days))
    n = len(rows)
    assert n >= 300, f"only {n} patients"
    ax = np.array([r[0] for r in rows])
    v = np.array([r[1] for r in rows])
    b = np.array([r[2] for r in rows])
    ep = np.array([r[3] for r in rows])
    pl = np.array([r[4] for r in rows])
    print(f"cohort with morphology + aetiology + findings: {n:,}   anoxic {100*ax.mean():.1f}%")

    # ---- E0 precondition ---------------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("E0  PRECONDITION — do the outcome and the predictor VARY in both arms? (rule 32)")
    print("=" * 100)
    print(f"   {'arm':>12} {'n':>7} {'epileptiform':>14} {'focal slowing':>15} "
          f"{'content mean':>14} {'content sd':>12}")
    ok = True
    for lab, m in (("anoxic", ax == 1), ("non-anoxic", ax == 0)):
        k = int(m.sum())
        pe, pp = 100 * ep[m].mean(), 100 * pl[m].mean()
        print(f"   {lab:>12} {k:>7,} {pe:>13.1f}% {pp:>14.1f}% {v[m].mean():>14.4f} {v[m].std():>12.4f}")
        if not (5 <= pe <= 95) or k < 200 or v[m].std() < 1e-9:
            ok = False
    if not ok:
        print("\n   *** A precondition failed — the interaction is not estimable and any null below is a")
        print("   statement about the cohort, not about the mechanism (rule 31).")

    Q = quintiles(b)
    one = np.ones(n)
    vz = z(v)

    def inter(outcome, reps=NBOOT):
        if not (0 < outcome.sum() < n):
            return None
        X = np.column_stack([one, Q, ax, vz, vz * ax])
        try:
            c = float(logit_fit(X, outcome)[-1])
        except Exception:
            return None
        out = []
        for _ in range(reps):
            i = rng.integers(0, n, n)
            if not (0 < outcome[i].sum() < n):
                continue
            vv = z(v[i])
            Xi = np.column_stack([np.ones(n), quintiles(b[i]), ax[i], vv, vv * ax[i]])
            try:
                cc = float(logit_fit(Xi, outcome[i])[-1])
            except Exception:
                continue
            if np.isfinite(cc):
                out.append(cc)
        if len(out) < reps // 4:
            return None
        lo, hi = np.percentile(out, [2.5, 97.5])
        return c, float(lo), float(hi)

    # ---- E1 / E2 -----------------------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("E1 / E2  AETIOLOGY x CONTENT, predicting a FINDING rather than death")
    print("=" * 100)
    e1 = inter(ep)
    e2 = inter(pl)
    for lab, r in (("epileptiform (GPD/LPD/seizure)  PRIMARY", e1),
                   ("focal slowing                   PLACEBO", e2)):
        if r is None:
            print(f"   {lab:>42}: not estimable")
        else:
            print(f"   {lab:>42}: {r[0]:+.3f} [{r[1]:+.3f}, {r[2]:+.3f}]"
                  f"{'   excludes zero' if r[1] * r[2] > 0 else '   INCLUDES ZERO'}")

    # per-arm, model-free
    print("\n   model-free — AUC of intra-burst content for an EPILEPTIFORM finding, by arm:")
    for lab, m in (("anoxic", ax == 1), ("non-anoxic", ax == 0)):
        idx = np.flatnonzero(m)
        a0 = auc(v[idx], ep[idx])
        bs = []
        for _ in range(800):
            j = rng.choice(idx, len(idx), replace=True)
            a1 = auc(v[j], ep[j])
            if np.isfinite(a1):
                bs.append(a1)
        lo, hi = np.percentile(bs, [2.5, 97.5])
        star = "*" if (lo - .5) * (hi - .5) > 0 else " "
        print(f"      {lab:>12}: {a0:.3f} [{lo:.3f}, {hi:.3f}]{star}")

    # ---- E4 shared-waveform caveat -----------------------------------------------------------------
    print("\n" + "=" * 100)
    print("E4  SHARED-WAVEFORM CAVEAT — how much do the two measures overlap, per arm?")
    print("=" * 100)
    for lab, m in (("anoxic", ax == 1), ("non-anoxic", ax == 0)):
        print(f"   {lab:>12}: corr(content, epileptiform) = {np.corrcoef(v[m], ep[m])[0,1]:+.3f}   "
              f"content | epi+ {v[m & (ep == 1)].mean():.4f}   | epi- {v[m & (ep == 0)].mean():.4f}")
    print("   Overlap exists in BOTH arms by construction, so it cannot by itself produce a difference")
    print("   between them. E1 tests the difference, not the association.")

    # ---- E3 exploratory ----------------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("E3  EXPLORATORY (conditioning on a post-exposure variable — rule 13; descriptive only)")
    print("=" * 100)
    # death day was computed alongside every other field in the same loop, so no parallel
    # reconstruction of the patient list is needed -- that pattern is how row-misalignment bugs happen
    d30 = np.array([0.0 if r[5] is None else (1.0 if r[5] <= 30 else 0.0) for r in rows])
    have = np.array([r[5] is not None for r in rows])
    print(f"   {'stratum':>34} {'n':>7} {'AUC content -> 30-day death':>30}")
    for lab, m in (("anoxic, NO epileptiform finding", (ax == 1) & (ep == 0) & have),
                   ("anoxic, epileptiform present", (ax == 1) & (ep == 1) & have),
                   ("non-anoxic, NO epileptiform", (ax == 0) & (ep == 0) & have),
                   ("non-anoxic, epileptiform present", (ax == 0) & (ep == 1) & have)):
        idx = np.flatnonzero(m)
        if len(idx) < 80 or not (0 < d30[idx].sum() < len(idx)):
            print(f"   {lab:>34} {len(idx):>7,} {'(too small)':>30}")
            continue
        a0 = auc(v[idx], d30[idx])
        bs = []
        for _ in range(800):
            j = rng.choice(idx, len(idx), replace=True)
            a1 = auc(v[j], d30[j])
            if np.isfinite(a1):
                bs.append(a1)
        lo, hi = np.percentile(bs, [2.5, 97.5])
        star = "*" if (lo - .5) * (hi - .5) > 0 else " "
        print(f"   {lab:>34} {len(idx):>7,}   {a0:.3f} [{lo:.3f}, {hi:.3f}]{star}")

    # ---- verdict -----------------------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("VERDICT")
    print("=" * 100)
    if not ok or e1 is None:
        print("   NO VERDICT — a precondition failed (E0); nothing below is interpretable.")
    elif e2 is not None and e2[1] * e2[2] > 0 and (e1[0] * e2[0] > 0):
        print("   E1 NOT INTERPRETABLE — the PLACEBO fired in the same direction, so the statistic is")
        print("   tracking how much abnormality the reader described, not epileptogenicity specifically.")
        print(f"   (epileptiform {e1[0]:+.3f}, focal slowing {e2[0]:+.3f})")
    elif e1[1] * e1[2] > 0 and e1[0] > 0:
        print(f"   E1 SUPPORTS CANDIDATE C — intra-burst content is more strongly tied to epileptiform")
        print(f"   activity in anoxic patients ({e1[0]:+.3f} [{e1[1]:+.3f}, {e1[2]:+.3f}]), and the placebo")
        print(f"   is silent. A mechanism predicted a second, independent association and got it.")
    else:
        print(f"   E1 FAILS — {e1[0]:+.3f} [{e1[1]:+.3f}, {e1[2]:+.3f}]. Candidate C loses its only concrete")
        print("   handle in this dataset and should be DEMOTED, not kept alive on plausibility.")
    print("\n   This cannot show causation or interneuron loss specifically — epileptiform activity is a")
    print("   downstream marker compatible with several accounts.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
