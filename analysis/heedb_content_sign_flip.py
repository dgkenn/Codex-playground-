#!/usr/bin/env python3
"""Does intra-burst fast content mean OPPOSITE things after anoxia and after everything else?

WHERE THIS CAME FROM, and it was not the question being asked. `heedb_thalamocortical_test.py` registered T2 as
a consistency check -- if the clinician's slowing flag and our intra-burst 8-30 Hz measure index one
thalamocortical factor, their aetiology interactions should share a sign. They do not. The flag's interaction
is **-0.750 [-1.433, -0.116]** and the intra-burst measure's is **+4.319 [+2.373, +6.754]**, implying a main
effect of **-2.435 in non-anoxic** and **+1.884 in anoxic**: the association with death REVERSES.

WHY THIS MATTERS IF IT IS REAL. N10 is a standing negative -- burst morphology's predictive increment was
**+0.070 [+0.006, +0.121] in I-CARE** but **+0.036 [-0.019, +0.076] in HEEDB**, and the inconsistency has never
been explained. I-CARE is **entirely cardiac arrest**, i.e. entirely anoxic; HEEDB is 54.6 % anoxic and 45.4 %
everything else. If the sign flips by aetiology, a mixed cohort averages two opposing effects toward zero and
a pure-anoxic cohort does not. **One previously unexplained negative would become a prediction.**

WHY IT PROBABLY IS NOT REAL, which is the reason for this file. Catalogue rule 16, paid for earlier in this
project: *when two arms of the same test disagree in SIGN, the definition is doing the work, not the biology.*
A logistic interaction is exactly where that failure hides -- the two strata differ in death rate (81.7 % vs
51.5 %), in burden, and in who survives the L1 exclusion at all. So every check below is designed to strip the
model away and ask whether the reversal is present in the raw data.

  S1  DISTRIBUTIONS FIRST. Median burden, median intra-burst content, and the L1 exclusion rate by aetiology.
      A reversal built on non-overlapping ranges is not a reversal.
  S2  NON-PARAMETRIC. AUC of intra-burst content for 30-day death, computed separately in anoxic and
      non-anoxic. No model, no link function, no adjustment. **If the reversal is real, this is above 0.5 in
      one arm and below 0.5 in the other.** If both sit on the same side of 0.5, the flip was the logistic
      scale and this line of work stops here.
  S3  WITHIN BURDEN STRATA. Burden differs by aetiology and gates the L1 exclusion, so the reversal must be
      shown to survive inside strata where burden is held roughly constant.
  S4  EXTERNAL CHECK, and it is the one that matters. I-CARE is all cardiac arrest. If the anoxic sign is
      real, the I-CARE association must run the SAME way as HEEDB's anoxic arm and OPPOSITE to its non-anoxic
      arm. This is a genuinely independent cohort and a prediction made before looking.

REGISTERED CONCLUSION RULE, fixed here so it cannot move afterwards: the reversal is credible only if S2 shows
AUCs straddling 0.5, S3 shows it inside at least two burden strata, and S4 replicates the anoxic direction in
I-CARE. Anything less and it is reported as a modelling artefact.
"""
import csv, io, os, sys
from collections import defaultdict
from datetime import datetime

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from icare_morph_replication import auc

AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
MORPH = os.environ.get("HEEDB_MORPH", "/tmp/eeg_probe/heedb_burst_morph.s*.csv")
BURDEN = os.environ.get("HEEDB_BURDEN", "/tmp/eeg_probe/heedb_bs_burden_win.s*.csv")
AETCACHE = os.environ.get("AET_CACHE", "/tmp/eeg_probe/heedb_aetiology.csv")
ICARE_MORPH = os.environ.get("ICARE_MORPH_OUT", "/tmp/eeg_probe/icare_morph2.csv")
ICARE_COHORT = os.environ.get("ICARE_COHORT", "/tmp/eeg_probe/icare_cohort.csv")
NBOOT = int(os.environ.get("NBOOT", "2000"))


def dt(s):
    s = (s or "").strip()
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, f)
        except ValueError:
            continue
    return None


def median_by_patient(pattern, col):
    import glob
    d = defaultdict(list)
    for path in sorted(glob.glob(pattern)):
        for r in csv.DictReader(open(path)):
            p = (r.get("patient") or "").strip()
            try:
                v = float(r[col])
            except (KeyError, TypeError, ValueError):
                continue
            if p.isdigit() and v == v:
                d[int(p)].append(v)
    return {p: float(np.median(v)) for p, v in d.items()}


def aetiology_map():
    """Cached, because the condition table is 1 GB and this is read repeatedly."""
    if os.path.exists(AETCACHE):
        out = {}
        for r in csv.DictReader(open(AETCACHE)):
            out[int(r["pid"])] = r["anoxic"] == "1"
        return out
    from heedb_bs_ascertainment import AETIOLOGY, norm
    anox = {}
    with open(f"{OMOP}/condition_occurrence.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                p = int(r["person_id"])
            except (KeyError, TypeError, ValueError):
                continue
            anox.setdefault(p, False)
            c = norm(r.get("condition_source_value"))
            if c and any(c.startswith(x) for x in AETIOLOGY["anoxic"]):
                anox[p] = True
    with open(AETCACHE, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["pid", "anoxic"])
        for p, v in anox.items():
            w.writerow([p, 1 if v else 0])
    return anox


def auc_ci(y, s, rng, reps):
    n = len(y); out = []
    for _ in range(reps):
        i = rng.integers(0, n, n)
        if 0 < y[i].sum() < n:
            a = auc(y[i], s[i])
            if a == a:
                out.append(a)
    if len(out) < 50:
        return float("nan"), float("nan")
    return tuple(np.percentile(out, [2.5, 97.5]))


def main():
    rng = np.random.default_rng(20260727)
    import boto3
    from botocore.config import Config
    s3 = boto3.client("s3", region_name="us-east-1",
                      config=Config(s3={"payload_signing_enabled": False}))
    when = {}
    for st in ("S0001", "S0002"):
        txt = s3.get_object(Bucket=AP,
                            Key=f"EEG/HEEDB_Metadata/{st}_EEG__reports_findings.csv"
                            )["Body"].read().decode("utf-8", "replace")
        for r in csv.DictReader(io.StringIO(txt)):
            p = (r.get("BDSPPatientID") or "").strip()
            if not p.isdigit():
                continue
            t = dt(r.get("EndTime(EEG)") or r.get("StartTime(EEG)") or "")
            p = int(p)
            if t and (p not in when or t < when[p]):
                when[p] = t
    death = {}
    with open(f"{OMOP}/death.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                death[int(r["person_id"])] = dt(r.get("death_datetime"))
            except (KeyError, TypeError, ValueError):
                pass

    anox = aetiology_map()
    ab = median_by_patient(MORPH, "alpha_beta")
    bur_all = median_by_patient(BURDEN, "burden")
    assert ab and bur_all, "feature tables empty"

    rows = []
    for p, v in ab.items():
        if p in when and p in death and death[p] is not None and p in bur_all:
            days = (death[p] - when[p]).days
            if days >= -1:
                rows.append((p, 1.0 if days <= 30 else 0.0, v, bur_all[p], 1.0 if anox.get(p) else 0.0))
    assert len(rows) >= 300, f"only {len(rows)} patients"
    y = np.array([r[1] for r in rows]); a = np.array([r[2] for r in rows])
    b = np.array([r[3] for r in rows]); ax = np.array([r[4] for r in rows])
    print(f"HEEDB cohort with intra-burst content: {len(y):,}   anoxic {100*ax.mean():.1f}%")

    # ---- S1 ---------------------------------------------------------------------------------------
    print("\n" + "=" * 96)
    print("S1  DISTRIBUTIONS -- is there enough overlap for a reversal to be meaningful?")
    print("=" * 96)
    everyone = set(bur_all)
    for lab, m in (("anoxic", ax == 1), ("non-anoxic", ax == 0)):
        print(f"   {lab:<11} n={int(m.sum()):>5}  30-d death {100*y[m].mean():5.1f}%  "
              f"median burden {np.median(b[m]):.3f}  median intra-burst {np.median(a[m]):.3f}  "
              f"IQR {np.percentile(a[m],25):.3f}-{np.percentile(a[m],75):.3f}")
    have_ab = set(ab)
    ex_an = [p for p in everyone if anox.get(p) and p not in have_ab]
    ex_no = [p for p in everyone if not anox.get(p) and p not in have_ab]
    tot_an = [p for p in everyone if anox.get(p)]
    tot_no = [p for p in everyone if not anox.get(p)]
    if tot_an and tot_no:
        print(f"   L1 exclusion (no measurable burst morphology): anoxic {100*len(ex_an)/len(tot_an):.1f}%  "
              f"non-anoxic {100*len(ex_no)/len(tot_no):.1f}%")
        print("   If those differ sharply, the two arms are conditioned differently and that alone can")
        print("   produce opposing associations.")

    # ---- S2 ---------------------------------------------------------------------------------------
    print("\n" + "=" * 96)
    print("S2  NON-PARAMETRIC -- AUC of intra-burst content for 30-day death, no model at all")
    print("=" * 96)
    verdict_s2 = False
    aucs = {}
    for lab, m in (("anoxic", ax == 1), ("non-anoxic", ax == 0)):
        A = auc(y[m], a[m])
        lo, hi = auc_ci(y[m], a[m], rng, NBOOT)
        aucs[lab] = (A, lo, hi)
        print(f"   {lab:<11} AUC {A:.3f} [{lo:.3f},{hi:.3f}]   "
              f"{'higher content -> MORE death' if A > 0.5 else 'higher content -> LESS death'}")
    if aucs["anoxic"][0] > 0.5 > aucs["non-anoxic"][0] or aucs["anoxic"][0] < 0.5 < aucs["non-anoxic"][0]:
        verdict_s2 = True
        print("   S2: the AUCs STRADDLE 0.5 -- the reversal is present in the raw ranking, not just the model.")
    else:
        print("   S2 FAILS: both arms lie on the same side of 0.5. The sign flip was the logistic scale and")
        print("   the interaction is not a reversal of association. This line stops here.")

    # ---- S3 ---------------------------------------------------------------------------------------
    print("\n" + "=" * 96)
    print("S3  WITHIN BURDEN STRATA -- burden differs by aetiology and gates the L1 exclusion")
    print("=" * 96)
    qs = np.quantile(b, [1 / 3, 2 / 3])
    edges = [-1e-9, qs[0], qs[1], 1.01]
    straddle = 0
    for i in range(3):
        m0 = (b > edges[i]) & (b <= edges[i + 1])
        line = f"   burden {edges[i]:.3f}-{edges[i+1]:.3f}  "
        vals = {}
        for lab, mm in (("anoxic", m0 & (ax == 1)), ("non-anoxic", m0 & (ax == 0))):
            k = int(mm.sum())
            if k < 60 or not (0 < y[mm].sum() < k):
                line += f"{lab} n={k} too few   "
                continue
            A = auc(y[mm], a[mm]); vals[lab] = A
            line += f"{lab} n={k:>4} AUC {A:.3f}   "
        print(line)
        if len(vals) == 2 and (vals["anoxic"] - 0.5) * (vals["non-anoxic"] - 0.5) < 0:
            straddle += 1
    print(f"   strata where the two aetiologies fall on OPPOSITE sides of 0.5: {straddle}/3")

    # ---- S4 ---------------------------------------------------------------------------------------
    print("\n" + "=" * 96)
    print("S4  EXTERNAL CHECK -- I-CARE is entirely cardiac arrest, so it must match the ANOXIC arm")
    print("=" * 96)
    coh = {}
    for r in csv.DictReader(open(ICARE_COHORT)):
        pid = (r.get("pid") or "").strip()
        try:
            c = float(r.get("cpc"))
        except (TypeError, ValueError):
            continue
        if pid and c == c:
            coh[pid] = 1.0 if c >= 3 else 0.0
    im = {}
    for r in csv.DictReader(open(ICARE_MORPH)):
        pid = (r.get("pid") or "").strip()
        try:
            im[pid] = float(r["alpha_beta"])
        except (KeyError, TypeError, ValueError):
            continue
    ids = sorted(p for p in im if p in coh)
    yi = np.array([coh[p] for p in ids]); ai = np.array([im[p] for p in ids])
    Ai = auc(yi, ai)
    loi, hii = auc_ci(yi, ai, rng, NBOOT)
    print(f"   I-CARE n={len(yi):,}   poor outcome {100*yi.mean():.1f}%")
    print(f"   AUC of intra-burst content for poor outcome {Ai:.3f} [{loi:.3f},{hii:.3f}]   "
          f"{'higher content -> WORSE' if Ai > 0.5 else 'higher content -> BETTER'}")
    an_auc = aucs["anoxic"][0]
    agree = (Ai - 0.5) * (an_auc - 0.5) > 0
    print(f"   HEEDB anoxic arm AUC {an_auc:.3f}   -> I-CARE {'AGREES' if agree else 'DISAGREES'} in direction")

    # ---- S5: the objection S1 raised and the registered rule failed to test --------------------------
    # The L1 exclusion rate differs enormously by aetiology (55.7 % vs 89.5 %), so the non-anoxic arm is a
    # far more selected subgroup. Differential selection can manufacture opposing associations on its own.
    # S3 matched on burden, but burden is not what gates the exclusion -- the BURST COUNT is. So stratify on
    # the variable that actually does the excluding.
    print("\n" + "=" * 96)
    print("S5  THE SELECTION OBJECTION -- stratify on BURST COUNT, which is what gates the L1 exclusion")
    print("=" * 96)
    nb = median_by_patient(MORPH, "n_bursts")
    keep = [i for i, r in enumerate(rows) if r[0] in nb]
    if len(keep) < 300:
        print("   burst counts unavailable -- cannot test")
        s5 = None
    else:
        j = np.array(keep)
        nbv = np.array([nb[rows[i][0]] for i in keep])
        yj, aj, axj = y[j], a[j], ax[j]
        qn = np.quantile(nbv, [1 / 3, 2 / 3])
        ed = [-1e-9, qn[0], qn[1], nbv.max() + 1]
        opp = 0; tested = 0
        for i in range(3):
            m0 = (nbv > ed[i]) & (nbv <= ed[i + 1])
            vals = {}
            line = f"   bursts {ed[i]:.0f}-{ed[i+1]:.0f}  "
            for lab, mm in (("anoxic", m0 & (axj == 1)), ("non-anoxic", m0 & (axj == 0))):
                k = int(mm.sum())
                if k < 50 or not (0 < yj[mm].sum() < k):
                    line += f"{lab} n={k} too few   "
                    continue
                A = auc(yj[mm], aj[mm]); vals[lab] = A
                line += f"{lab} n={k:>4} AUC {A:.3f}   "
            print(line)
            if len(vals) == 2:
                tested += 1
                if (vals["anoxic"] - 0.5) * (vals["non-anoxic"] - 0.5) < 0:
                    opp += 1
        print(f"   strata (matched on burst count) with the two aetiologies on OPPOSITE sides: {opp}/{tested}")
        s5 = tested > 0 and opp >= max(2, tested - 1)
        print(f"   {'The reversal survives matching on the exclusion variable itself.' if s5 else 'The reversal does NOT survive matching on burst count -- differential selection is a live explanation.'}")

    print("\n" + "=" * 96)
    print("VERDICT AGAINST THE RULE FIXED BEFORE RUNNING")
    print("=" * 96)
    ok = verdict_s2 and straddle >= 2 and agree
    print(f"   S2 straddles 0.5: {verdict_s2}     S3 opposite sides in >=2 strata: {straddle >= 2}     "
          f"S4 I-CARE agrees with anoxic: {agree}     S5 survives burst-count matching: {s5}")
    print(f"   {'PASSES the registered rule' if ok else 'FAILS the registered rule -- report as a modelling artefact'}")
    print("\n   TWO CAVEATS THE REGISTERED RULE DID NOT CAPTURE, stated because they weaken it:")
    print(f"   1. S4 required only DIRECTIONAL agreement. I-CARE's AUC is {Ai:.3f} [{loi:.3f},{hii:.3f}],")
    print("      which INCLUDES 0.5 -- so the external cohort is consistent with the anoxic direction but")
    print("      does not on its own establish it. That is weak corroboration, not replication.")
    print("   2. The L1 exclusion differs sharply by aetiology (55.7 % vs 89.5 %), so the non-anoxic arm is")
    print("      a far more selected subgroup. S5 addresses this directly; read the verdict there, not the")
    print("      headline.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
