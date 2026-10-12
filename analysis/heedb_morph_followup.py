#!/usr/bin/env python3
"""Is burst morphology really an INDEPENDENT prognostic axis, or is it re-measuring things we already have?

WHAT PROMPTED THIS. The morphology analysis found three things that only make sense together:
  * morphology DIFFERS by aetiology (post-anoxic bursts more stereotyped, +0.222 SD; spectrally faster, +0.379 SD)
  * morphology PREDICTS death among burst-suppression patients (AUC 0.671 [0.642,0.704])
  * morphology absorbs only 1.4 % of the aetiology effect on mortality
Differing by aetiology and predicting death, while explaining almost none of the aetiology effect, means
morphology carries information that is largely ORTHOGONAL to aetiology. That is a more useful claim than the
mediation one it replaced -- but it is also a much easier claim to make spuriously, so it is attacked here before
it is believed.

THE THREE WAYS THIS CLAIM COULD BE FALSE, tested in order of how likely they are to kill it.

  G1  IT IS BURDEN IN DISGUISE. Burst duration was the strongest predictor (-12.09 pp/SD) and burst duration is
      MECHANICALLY entangled with suppression burden: if bursts are shorter, a larger fraction of the record is
      suppressed. Burden was NOT in the model that produced AUC 0.671. If the morphology coefficients collapse
      once burden is included, the "independent axis" is an artefact of an omitted variable.
      FALSIFIED IF the morphology coefficients lose significance, or the incremental AUC over a model containing
      burden fails to exclude zero.

  G2  IT IS IN-SAMPLE OPTIMISM. AUC 0.671 was computed on the data that fitted it. Five features on ~1,400
      patients will always separate somewhat.
      Tested by CROSS-SITE validation -- fit at one hospital, evaluate at the other. This is the strongest
      external check available in this dataset, since the sites have separate populations, EEG services and
      readers.
      FALSIFIED IF out-of-sample AUC < 0.62 or its interval includes 0.5.

  G3  IT IS ONE AETIOLOGY WEARING A DISGUISE. If morphology only predicts death within post-anoxic patients, it
      is not an independent axis, it is an anoxia detector.
      FALSIFIED IF morphology fails to predict within at least one NON-anoxic aetiology.

  Also reported, not a formal test: the correlation matrix among the features and burden, so any collinearity
  driving the results is visible rather than inferred.

REGISTERED EXPECTATION. G1 is the one I expect to be closest. Burst duration and burden are two views of the same
underlying quantity, and if the incremental value survives at all I expect it to be much smaller than the
standalone AUC suggests. Saying so in advance so that a shrunken effect is not narrated afterwards as a success.

EXPLAINABILITY. Every model here is linear on named physiological features with signed coefficients. Incremental
value is reported as a change in AUC with a paired bootstrap interval, not as a claim that any model is fit for
clinical use.
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
NBOOT = int(os.environ.get("NBOOT", "1000"))
FEATS = ["stereotypy", "alpha_beta", "burst_amp", "burst_dur", "burst_rate"]
AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"


def lpm(X, y):
    return np.linalg.lstsq(X, y, rcond=None)[0]


def auc(y, s):
    y = np.asarray(y, float); s = np.asarray(s, float)
    n1 = float(y.sum()); n0 = float(len(y) - n1)
    if n1 == 0 or n0 == 0:
        return float("nan")
    o = np.argsort(s, kind="mergesort"); r = np.empty(len(s), float); r[o] = np.arange(1, len(s) + 1)
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def main():
    rng = np.random.default_rng(20260726)

    morph, site = {}, {}
    for f in sorted(glob.glob("/tmp/eeg_probe/heedb_burst_morph*.csv")):
        for r in csv.DictReader(open(f)):
            try:
                p = int(r["patient"])
            except Exception:
                continue
            d = {}
            ok = True
            for k in FEATS + ["burden"]:
                try:
                    d[k] = float(r[k])
                except Exception:
                    ok = False
            if ok and all(v == v for v in d.values()):
                morph[p] = d
                site[p] = r["site"]

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

    import boto3
    from botocore.config import Config
    s3 = boto3.client("s3", region_name="us-east-1",
                      config=Config(s3={"payload_signing_enabled": False}))
    when, age, fem = {}, {}, {}
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
            if p not in when or t < when[p]:
                when[p] = t
                try:
                    age[p] = float(r.get("AgeAtVisit") or "nan")
                except Exception:
                    age[p] = float("nan")
                fem[p] = 1.0 if r.get("SexDSC") == "Female" else 0.0

    keys = list(AETIOLOGY)
    rows = []
    for p, d in morph.items():
        if p not in cond_seen:
            continue
        dd, t = death.get(p), when.get(p)
        if dd is None or t is None:
            continue
        days = (dd - t).days
        if days < -1:
            continue
        a = age.get(p, float("nan"))
        rows.append(dict(pid=p, site=site.get(p, "?"), d30=1.0 if days <= 30 else 0.0,
                         age=(0.0 if a != a else (a - 60.0) / 15.0), fem=fem.get(p, 0.0),
                         labs=aet.get(p, set()), **d))
    n = len(rows)
    print(f"analysable: {n:,}   died within 30 d: {100*np.mean([r['d30'] for r in rows]):.1f} %")
    print(f"   by site: " + ", ".join(f"{s}={sum(1 for r in rows if r['site']==s)}"
                                      for s in sorted(set(r['site'] for r in rows))))
    if n < 400:
        print("*** insufficient"); return 1

    Z = {}
    for k in FEATS + ["burden"]:
        v = np.asarray([r[k] for r in rows], float)
        Z[k] = (v - v.mean()) / (v.std() if v.std() > 1e-12 else 1.0)
    y = np.asarray([r["d30"] for r in rows], float)
    expo = [k for k in keys if sum(1 for r in rows if k in r["labs"]) >= 30]

    print("\n=== correlation of each feature with BURDEN (the collinearity that matters) ===")
    for k in FEATS:
        print(f"   {k:11s} r = {np.corrcoef(Z[k], Z['burden'])[0,1]:+.3f}")

    def build(idx, with_morph, with_burden=True):
        cols = [np.ones(len(idx))]
        for k in expo:
            cols.append(np.asarray([1.0 if k in rows[i]["labs"] else 0.0 for i in idx], float))
        cols.append(np.asarray([rows[i]["age"] for i in idx], float))
        cols.append(np.asarray([rows[i]["fem"] for i in idx], float))
        if with_burden:
            cols.append(Z["burden"][idx])
        if with_morph:
            for k in FEATS:
                cols.append(Z[k][idx])
        return np.column_stack(cols)

    allidx = np.arange(n)

    # ---- G1: does morphology survive adjustment for burden? ----------------------------------------
    print("\n" + "=" * 78)
    print("G1  IS IT BURDEN IN DISGUISE? morphology coefficients WITH burden in the model")
    print("=" * 78)
    Xw = build(allidx, True, True)
    bw = lpm(Xw, y)
    bt = defaultdict(list)
    for _ in range(NBOOT):
        i = rng.integers(0, n, n)
        try:
            b2 = lpm(build(i, True, True), y[i])
        except Exception:
            continue
        for j in range(len(bw)):
            bt[j].append(b2[j])
    base_len = 1 + len(expo) + 2
    print(f"   {'burden':11s} {100*bw[base_len]:+7.2f} pp/SD "
          f"[{100*np.percentile(bt[base_len],2.5):+7.2f},{100*np.percentile(bt[base_len],97.5):+7.2f}]")
    surv = 0
    for j, k in enumerate(FEATS):
        c = base_len + 1 + j
        lo, hi = np.percentile(bt[c], [2.5, 97.5])
        sig = (lo > 0 or hi < 0)
        surv += sig
        print(f"   {k:11s} {100*bw[c]:+7.2f} pp/SD [{100*lo:+7.2f},{100*hi:+7.2f}] {'*' if sig else 'ns'}")
    # incremental AUC over a model that already contains burden
    a_base = auc(y, build(allidx, False, True) @ lpm(build(allidx, False, True), y))
    a_full = auc(y, Xw @ bw)
    dl = []
    for _ in range(NBOOT):
        i = rng.integers(0, n, n)
        if y[i].sum() in (0, len(i)):
            continue
        try:
            Xb, Xf = build(i, False, True), build(i, True, True)
            dl.append(auc(y[i], Xf @ lpm(Xf, y[i])) - auc(y[i], Xb @ lpm(Xb, y[i])))
        except Exception:
            continue
    lo, hi = np.percentile(dl, [2.5, 97.5])
    print(f"\n   AUC without morphology (aetiology+age+sex+burden): {a_base:.3f}")
    print(f"   AUC with morphology added                        : {a_full:.3f}")
    print(f"   incremental AUC {a_full-a_base:+.3f} [{lo:+.3f},{hi:+.3f}]")
    print(f"   G1 {'CONFIRMED' if (lo > 0 and surv >= 1) else 'FALSIFIED'} "
          f"({surv}/5 morphology features remain significant with burden in the model)")

    # ---- G2: cross-site out-of-sample ---------------------------------------------------------------
    print("\n" + "=" * 78)
    print("G2  OUT-OF-SAMPLE: fit at one hospital, evaluate at the other")
    print("=" * 78)
    sites = sorted(set(r["site"] for r in rows))
    for tr in sites:
        itr = np.array([i for i in range(n) if rows[i]["site"] == tr])
        ite = np.array([i for i in range(n) if rows[i]["site"] != tr])
        if len(itr) < 200 or len(ite) < 150 or y[ite].sum() < 20:
            print(f"   train {tr}: too few for a split"); continue
        b = lpm(build(itr, True, True), y[itr])
        sc = build(ite, True, True) @ b
        a = auc(y[ite], sc)
        ab = []
        for _ in range(NBOOT):
            j = rng.integers(0, len(ite), len(ite))
            if y[ite][j].sum() in (0, len(j)):
                continue
            ab.append(auc(y[ite][j], sc[j]))
        lo2, hi2 = np.percentile(ab, [2.5, 97.5])
        print(f"   train {tr} (n={len(itr)}) -> test other (n={len(ite)}): AUC {a:.3f} [{lo2:.3f},{hi2:.3f}] "
              f"{'PASS' if (a >= 0.62 and lo2 > 0.5) else 'FAIL'}")

    # ---- G3: does it work within non-anoxic aetiologies? --------------------------------------------
    print("\n" + "=" * 78)
    print("G3  WITHIN-AETIOLOGY: is morphology an anoxia detector, or a general axis?")
    print("=" * 78)
    for k in expo:
        idx = np.array([i for i in range(n) if k in rows[i]["labs"]])
        if len(idx) < 120 or y[idx].sum() < 25 or (len(idx) - y[idx].sum()) < 25:
            continue
        X = np.column_stack([np.ones(len(idx)), Z["burden"][idx]] + [Z[f][idx] for f in FEATS])
        b = lpm(X, y[idx])
        a = auc(y[idx], X @ b)
        ab = []
        for _ in range(NBOOT):
            j = rng.integers(0, len(idx), len(idx))
            if y[idx][j].sum() in (0, len(j)):
                continue
            try:
                ab.append(auc(y[idx][j], X[j] @ lpm(X[j], y[idx][j])))
            except Exception:
                continue
        lo3, hi3 = np.percentile(ab, [2.5, 97.5])
        print(f"   {k:12s} n={len(idx):5d}  AUC {a:.3f} [{lo3:.3f},{hi3:.3f}] "
              f"{'*' if lo3 > 0.5 else 'ns'}")
    print("\n   G3 passes if at least one NON-anoxic aetiology shows an interval above 0.5.")
    print("\n   Cross-site AUC is the only figure here that is not optimistic; the within-aetiology and")
    print("   incremental figures are in-sample and should be read as upper bounds.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
