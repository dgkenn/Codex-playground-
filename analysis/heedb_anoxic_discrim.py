#!/usr/bin/env python3
"""Within post-anoxic burst suppression: what separates death in three days from survival past six months?

WHY THIS IS NOW THE QUESTION. The landmark analysis showed the aetiology excess is EXHAUSTED among 30-day
survivors (gap +0.832 from the EEG, +0.217 at a day-30 landmark, -0.206 at day 180), and that post-anoxic
burst-suppression patients split sharply: 40.6 % dead within three days, 18.8 % alive past 180. That is a fixed
subgroup whose outcome is largely settled at the recording, so the useful question stopped being "why does
suppression mean more after anoxia" and became "which of these patients is in which group". It is a
within-anoxic discrimination problem, and burden, morphology, coexisting findings and persistence are all
already measured on exactly these patients.

WHAT IS AT STAKE. If measured burden alone separates them, the aetiology comparison was a detour and the
dose-response is the finding -- simpler, and already established. If burden does NOT separate them, something
else visible on the EEG does, and the morphology features get a properly targeted second chance: they were
previously asked to explain a cross-aetiology gap, which is not what they are for.

DESIGN, and the trap it exists to avoid.
  * The primary outcome is death within 3 days of the index EEG, and the contrast group is survival past 180
    days. The intermediate group is reported but not modelled, because the question is about the two ends.
  * PERSISTENCE CANNOT BE USED FOR THE 3-DAY OUTCOME. A patient must survive long enough to have a second EEG,
    so "suppression persisted" is unavailable to anyone who died on day 2 -- immortal time, and it would
    manufacture a strong spurious predictor. Persistence is therefore tested SEPARATELY, in a landmark design
    among patients alive at their follow-up recording, asking about death after that point.
  * DISCRIMINATION IS REPORTED OUT OF SAMPLE. Every AUC quoted for a multi-feature model is cross-validated
    (5-fold) and additionally validated ACROSS HOSPITALS, because an in-sample AUC on five features and a few
    hundred patients is optimistic by construction. An earlier morphology result in this project reported
    AUC 0.671 in-sample and collapsed to +0.008 incremental once the obvious parent variable was included.
  * EXPLAINABILITY. Linear models on named physiological quantities, coefficients in percentage points per
    standard deviation. No learned representation.

REGISTERED EXPECTATION. Burden is expected to do most of the work, because the dose-response within anoxic
patients is already steep and monotone (3-day death should track it). The interesting outcome is the INCREMENT
from morphology and coexisting findings over burden. Stated in advance so a small increment is not narrated
afterwards as a success: an increment below +0.02 cross-validated AUC is not a finding.

NOTE (2026-07-26): the 40.6 % / 18.8 % split quoted here comes from the LEGACY exposure, in which a
patient counted as suppressed if ANY of their recordings said so. Measured at the index recording the
split is 45.6 % / 15.2 % -- a sharper early mass, not a softer one. This script still carries the
legacy aggregation (see docs/research/41_RESULTS_LEDGER.md R289) and its numbers are not corrected.
"""
import csv, glob, io, os, sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from heedb_bs_ascertainment import AETIOLOGY, norm, dt
# The sandbox exports placeholder AWS_* env vars that shadow the real profile -- common/awsenv.py.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.awsenv import sanitize as _aws_sanitize; _aws_sanitize()

OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
NBOOT = int(os.environ.get("NBOOT", "600"))
AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
FEATS = ["stereotypy", "alpha_beta", "burst_amp", "burst_dur", "burst_rate"]
FIND = ["gpd", "lpd", "seizure", "gen slowing", "pdr"]


def lpm(X, y):
    return np.linalg.lstsq(X, y, rcond=None)[0]


def auc(y, s):
    y = np.asarray(y, float); s = np.asarray(s, float)
    n1 = float(y.sum()); n0 = float(len(y) - n1)
    if n1 == 0 or n0 == 0:
        return float("nan")
    o = np.argsort(s, kind="mergesort"); r = np.empty(len(s), float); r[o] = np.arange(1, len(s) + 1)
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def cv_auc(X, y, rng, folds=5):
    idx = rng.permutation(len(y))
    out = []
    for f in range(folds):
        te = idx[f::folds]; tr = np.setdiff1d(idx, te)
        if y[tr].sum() < 5 or y[te].sum() < 3:
            continue
        try:
            out.append(auc(y[te], X[te] @ lpm(X[tr], y[tr])))
        except Exception:
            continue
    return float(np.nanmean(out)) if out else float("nan")


def main():
    rng = np.random.default_rng(20260726)

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

    burden, morph = {}, {}
    for f in sorted(glob.glob("/tmp/eeg_probe/heedb_bs_burden*.csv")):
        for r in csv.DictReader(open(f)):
            try:
                p, v = int(r["patient"]), float(r["burden"])
            except Exception:
                continue
            if v == v:
                burden[p] = max(burden.get(p, 0.0), v)
    for f in sorted(glob.glob("/tmp/eeg_probe/heedb_burst_morph*.csv")):
        for r in csv.DictReader(open(f)):
            try:
                p = int(r["patient"])
            except Exception:
                continue
            d, ok = {}, True
            for k in FEATS:
                try:
                    d[k] = float(r[k])
                except Exception:
                    ok = False
            if ok and all(v == v for v in d.values()):
                morph[p] = d

    import boto3
    from botocore.config import Config
    s3 = boto3.client("s3", region_name="us-east-1",
                      config=Config(s3={"payload_signing_enabled": False}))
    reps = defaultdict(list)
    site, age = {}, {}
    for st in ("S0001", "S0002"):
        txt = s3.get_object(Bucket=AP,
                            Key=f"EEG/HEEDB_Metadata/{st}_EEG__reports_findings.csv"
                            )["Body"].read().decode("utf-8", "replace")
        for r in csv.DictReader(io.StringIO(txt)):
            p = (r.get("BDSPPatientID") or "").strip()
            if not p.isdigit():
                continue
            p = int(p)
            t = dt(r.get("EndTime(EEG)") or r.get("StartTime(EEG)") or "")
            if t is None:
                continue
            has = lambda k: (r.get(k) or "").strip() not in ("", "None", "nan")
            reps[p].append((t, has("bs"), {k: has(k) for k in FIND}))
            if p not in site:
                site[p] = st
                try:
                    age[p] = float(r.get("AgeAtVisit") or "nan")
                except Exception:
                    age[p] = float("nan")
    for p in reps:
        reps[p].sort(key=lambda x: x[0])

    rows = []
    for p, v in reps.items():
        if p not in cond_seen or "anoxic" not in aet.get(p, set()):
            continue
        if not any(x[1] for x in v):
            continue                                   # burst suppression somewhere
        d = death.get(p)
        if d is None:
            continue
        idx = next(x for x in v if x[1])               # index = earliest recording with suppression
        days = (d - idx[0]).days
        if days < -1:
            continue
        fu = next(((t, b) for t, b, _ in v if t > idx[0]), None)
        a = age.get(p, float("nan"))
        rows.append(dict(pid=p, site=site.get(p, "?"), days=float(days),
                         d3=1.0 if days <= 3 else 0.0, alive180=1.0 if days > 180 else 0.0,
                         bur=burden.get(p, float("nan")),
                         age=(0.0 if a != a else (a - 60.0) / 15.0),
                         fu_t=(fu[0] if fu else None), fu_bs=(1.0 if (fu and fu[1]) else 0.0),
                         **{k: (1.0 if idx[2].get(k) else 0.0) for k in FIND},
                         **{k: morph.get(p, {}).get(k, float("nan")) for k in FEATS}))
    n = len(rows)
    d3 = sum(r["d3"] for r in rows); a180 = sum(r["alive180"] for r in rows)
    print(f"post-anoxic burst-suppression patients: {n:,}")
    print(f"   dead within 3 days: {int(d3)} ({100*d3/n:.1f} %)   alive past 180 days: "
          f"{int(a180)} ({100*a180/n:.1f} %)   in between: {n-int(d3)-int(a180)}")

    # ---- descriptive contrast of the two ends -------------------------------------------------------
    print("\n" + "=" * 92)
    print("THE TWO ENDS COMPARED  (index-recording features)")
    print("=" * 92)
    early = [r for r in rows if r["d3"] == 1.0]
    late = [r for r in rows if r["alive180"] == 1.0]
    print(f"   {'feature':14s} {'dead <=3 d':>14s} {'alive >180 d':>14s} {'difference':>12s}")
    for k in ["bur"] + FEATS + FIND + ["age"]:
        a = [r[k] for r in early if r[k] == r[k]]
        b = [r[k] for r in late if r[k] == r[k]]
        if len(a) < 15 or len(b) < 15:
            continue
        print(f"   {k:14s} {np.mean(a):13.3f} {np.mean(b):13.3f} {np.mean(a)-np.mean(b):+11.3f}")

    # ---- discrimination, cross-validated ------------------------------------------------------------
    print("\n" + "=" * 92)
    print("DISCRIMINATION FOR 3-DAY DEATH  (5-fold cross-validated; in-sample shown for contrast)")
    print("=" * 92)
    gb = [r for r in rows if r["bur"] == r["bur"]]
    if len(gb) >= 200:
        y = np.asarray([r["d3"] for r in gb], float)
        bur = np.asarray([r["bur"] for r in gb], float)
        fnd = np.column_stack([np.asarray([r[k] for r in gb], float) for k in FIND])
        agev = np.asarray([r["age"] for r in gb], float)
        models = [("burden alone", np.column_stack([np.ones(len(gb)), bur])),
                  ("burden + age", np.column_stack([np.ones(len(gb)), bur, agev])),
                  ("burden + age + findings", np.column_stack([np.ones(len(gb)), bur, agev, fnd]))]
        for nm, X in models:
            print(f"   {nm:28s} n={len(gb):5d}  CV AUC {cv_auc(X, y, rng):.3f}   "
                  f"(in-sample {auc(y, X @ lpm(X, y)):.3f})")
        gm = [r for r in gb if r["stereotypy"] == r["stereotypy"]]
        if len(gm) >= 150:
            ym = np.asarray([r["d3"] for r in gm], float)
            Z = {}
            for k in FEATS:
                v = np.asarray([r[k] for r in gm], float)
                Z[k] = (v - v.mean()) / (v.std() if v.std() > 1e-12 else 1.0)
            X1 = np.column_stack([np.ones(len(gm)), np.asarray([r["bur"] for r in gm], float)])
            X2 = np.column_stack([X1] + [Z[k] for k in FEATS])
            c1, c2 = cv_auc(X1, ym, rng), cv_auc(X2, ym, rng)
            print(f"   {'burden alone (morph subset)':28s} n={len(gm):5d}  CV AUC {c1:.3f}")
            print(f"   {'burden + morphology':28s} n={len(gm):5d}  CV AUC {c2:.3f}   "
                  f"increment {c2-c1:+.3f}   {'FINDING' if c2-c1 >= 0.02 else 'not a finding (<0.02)'}")
            bm = lpm(X2, ym)
            for j, k in enumerate(FEATS, 2):
                print(f"      {k:11s} {100*bm[j]:+7.2f} pp/SD")
        # cross-site
        print("\n   cross-hospital validation (burden + age + findings):")
        Xf = models[2][1]
        sarr = np.array([r["site"] for r in gb])
        for tr in sorted(set(sarr)):
            itr = np.where(sarr == tr)[0]; ite = np.where(sarr != tr)[0]
            if len(itr) < 100 or len(ite) < 80 or y[ite].sum() < 15:
                continue
            print(f"      train {tr} (n={len(itr)}) -> test other (n={len(ite)}): "
                  f"AUC {auc(y[ite], Xf[ite] @ lpm(Xf[itr], y[itr])):.3f}")

    # ---- persistence, landmarked --------------------------------------------------------------------
    print("\n" + "=" * 92)
    print("PERSISTENCE, LANDMARKED  (only patients alive at their follow-up recording)")
    print("=" * 92)
    lm = [r for r in rows if r["fu_t"] is not None]
    print(f"   post-anoxic burst-suppression patients with a later recording: {len(lm):,}")
    print("   (persistence cannot be used for the 3-day outcome: a patient must survive to have a second EEG,")
    print("    so it is unavailable to anyone who died on day 2 -- immortal time)")
    if len(lm) >= 200:
        for k in (30, 90):
            a = [r for r in lm if r["fu_bs"] == 1.0]
            b = [r for r in lm if r["fu_bs"] == 0.0]
            if len(a) < 30 or len(b) < 30:
                continue
            ya = np.mean([1.0 if r["days"] <= k else 0.0 for r in a])
            yb = np.mean([1.0 if r["days"] <= k else 0.0 for r in b])
            print(f"   death within {k:3d} d of the INDEX EEG: suppression persisted {100*ya:.1f} % "
                  f"(n={len(a)})  resolved {100*yb:.1f} % (n={len(b)})  difference {100*(ya-yb):+.1f} pp")
    print("\n   Registered expectation was that burden does most of the work and the interesting number is the")
    print("   INCREMENT from morphology; an increment below +0.02 cross-validated AUC is not a finding.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
