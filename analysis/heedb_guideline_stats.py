#!/usr/bin/env python3
"""The headline result under proper statistics: logistic model, calibration, clustering, and the missing CI.

WHY THIS EXISTS. `heedb_vs_guideline.py` established the finding but does so with machinery that a statistician
will object to on sight, and three of the objections are fair:

  * LINEAR PROBABILITY MODELS for a binary outcome. Predictions can fall outside [0,1] and the error structure
    is wrong. Used originally because it is dependency-free and its coefficients read directly in percentage
    points -- convenient, and not a defence.
  * DISCRIMINATION ONLY. Every reported number is an AUC. A score can rank patients perfectly and still be
    badly wrong about their absolute risk, and it is absolute risk that a clinician would act on. No
    calibration has ever been reported.
  * NO CONFIDENCE INTERVAL ON THE MORPHOLOGY INCREMENT (+0.041), alone among the headline numbers.

  S1  Refit the guideline comparison with LOGISTIC regression and confirm the increment survives.
  S2  CALIBRATION of the category+burden model: calibration-in-the-large, calibration slope, and observed
      versus predicted risk by decile.
  S3  Bootstrap CI on the morphology increment, resampling PATIENTS rather than recordings.
  S4  CLUSTERING. Patients contribute more than one recording. The index-only analysis already gives one row
      per patient, so this reports how much clustering there would have been -- i.e. whether the point is moot.

Logistic regression is implemented by IRLS in numpy rather than pulling in statsmodels, to keep this runnable
in the same dependency-light environment as the rest of the analysis directory.
"""
import csv, glob, io, os, sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from heedb_bs_ascertainment import AETIOLOGY, norm, dt

OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
NBOOT = int(os.environ.get("NBOOT", "500"))
AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
FEATS = ("stereotypy", "alpha_beta", "burst_amp", "burst_dur", "burst_rate")


def logit_fit(X, y, iters=60, ridge=1e-6):
    """Logistic regression by iteratively reweighted least squares, with a whisper of ridge for stability."""
    b = np.zeros(X.shape[1])
    for _ in range(iters):
        eta = np.clip(X @ b, -30, 30)
        p = 1.0 / (1.0 + np.exp(-eta))
        w = np.clip(p * (1 - p), 1e-9, None)
        z = eta + (y - p) / w
        WX = X * w[:, None]
        A = X.T @ WX + ridge * np.eye(X.shape[1])
        try:
            nb = np.linalg.solve(A, X.T @ (w * z))
        except np.linalg.LinAlgError:
            break
        if not np.all(np.isfinite(nb)) or np.max(np.abs(nb - b)) < 1e-8:
            b = nb if np.all(np.isfinite(nb)) else b
            break
        b = nb
    return b


def predict(X, b):
    return 1.0 / (1.0 + np.exp(-np.clip(X @ b, -30, 30)))


def auc(y, s):
    y = np.asarray(y, float); s = np.asarray(s, float)
    n1 = float(y.sum()); n0 = float(len(y) - n1)
    if n1 == 0 or n0 == 0:
        return float("nan")
    o = np.argsort(s, kind="mergesort"); r = np.empty(len(s), float); r[o] = np.arange(1, len(s) + 1)
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def cv_pred(X, y, rng, folds=5, reps=5):
    """Out-of-fold predictions, averaged over repeats -- used for both AUC and calibration."""
    acc = np.zeros(len(y)); cnt = np.zeros(len(y))
    for _ in range(reps):
        idx = rng.permutation(len(y))
        for f in range(folds):
            te = idx[f::folds]; tr = np.setdiff1d(idx, te)
            if y[tr].sum() < 5 or (len(tr) - y[tr].sum()) < 5:
                continue
            b = logit_fit(X[tr], y[tr])
            acc[te] += predict(X[te], b); cnt[te] += 1
    ok = cnt > 0
    out = np.full(len(y), np.nan)
    out[ok] = acc[ok] / cnt[ok]
    return out, ok


def main():
    rng = np.random.default_rng(20260726)

    # ---- same cohort construction as the corrected headline analysis: INDEX recording only ----------
    bsess = defaultdict(dict)
    for f in sorted(glob.glob("/tmp/eeg_probe/heedb_bs_burden*.csv")):
        for r in csv.DictReader(open(f)):
            try:
                p, s, v = int(r["patient"]), int(r["session"]), float(r["burden"])
            except Exception:
                continue
            if v == v:
                bsess[p][s] = max(bsess[p].get(s, 0.0), v)

    morph = {}
    for f in sorted(glob.glob("/tmp/eeg_probe/heedb_burst_morph*.csv")):
        for r in csv.DictReader(open(f)):
            try:
                p = int(r["patient"]); s = int(r["session"])
            except Exception:
                continue
            d, ok = {}, True
            for k in FEATS:
                try:
                    d[k] = float(r[k])
                except Exception:
                    ok = False
            if ok and all(v == v for v in d.values()):
                if p not in morph or s < morph[p]["_s"]:
                    morph[p] = dict(d, _s=s)

    death = {}
    with open(f"{OMOP}/death.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                death[int(r["person_id"])] = dt(r.get("death_datetime"))
            except Exception:
                pass

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

    import boto3
    from botocore.config import Config
    s3 = boto3.client("s3", region_name="us-east-1",
                      config=Config(s3={"payload_signing_enabled": False}))
    stime = {}
    for st in ("S0001", "S0002"):
        txt = s3.get_object(Bucket=AP,
                            Key=f"EEG/eeg-metadata/{st}_eeg_metadata_2026_04_30.csv"
                            )["Body"].read().decode("utf-8", "replace")
        for r in csv.DictReader(io.StringIO(txt)):
            p = (r.get("BDSPPatientID") or "").strip(); s = (r.get("SessionID") or "").strip()
            if p.isdigit() and s.isdigit():
                t = dt(r.get("StartTime") or r.get("EndTime") or "")
                if t is not None:
                    stime[(int(p), int(s))] = t

    burden = {}
    for p, d in bsess.items():
        times = {s: stime[(p, s)] for s in d if (p, s) in stime}
        s0 = min(times, key=lambda s: times[s]) if times else min(d)
        burden[p] = d[s0]

    FL = ("bs", "low voltage", "gpd", "lpd", "grda", "lrda", "seizure", "status")
    when, Fidx, site = {}, {}, {}
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
                when[p] = t; site[p] = st
                Fidx[p] = {k: ((r.get(k) or "").strip() not in ("", "None", "nan")) for k in FL}

    def westhall(f):
        if f.get("bs") or f.get("low voltage"):
            return 2
        if any(f.get(k) for k in ("gpd", "lpd", "grda", "lrda", "seizure", "status")):
            return 1
        return 0

    rows = []
    for p, t0 in when.items():
        if p not in cond_seen or "anoxic" not in aet.get(p, set()):
            continue
        d = death.get(p)
        if d is None:
            continue
        days = (d - t0).days
        if days < -1:
            continue
        rows.append(dict(pid=p, site=site.get(p, "?"), d3=1.0 if days <= 3 else 0.0,
                         cat=westhall(Fidx[p]), bur=burden.get(p, float("nan")),
                         **{k: morph.get(p, {}).get(k, float("nan")) for k in FEATS}))
    print(f"post-anoxic patients with an ascertained death: {len(rows):,}  "
          f"(one row per patient -- index recording only)")

    g = [r for r in rows if r["bur"] == r["bur"]]
    n = len(g)
    y = np.asarray([r["d3"] for r in g], float)
    one = np.ones(n)
    cat = np.asarray([r["cat"] for r in g], float)
    bur = np.asarray([r["bur"] for r in g], float)
    Xc = np.column_stack([one, (cat == 1).astype(float), (cat == 2).astype(float)])
    Xcb = np.column_stack([Xc, bur])
    print(f"   with a measured burden: {n:,}   3-day deaths: {int(y.sum()):,} ({100*y.mean():.1f}%)")

    # ---- S1: logistic ------------------------------------------------------------------------------
    print("\n" + "=" * 92)
    print("S1  LOGISTIC REGRESSION -- does the increment survive a proper link function?")
    print("=" * 92)
    pc, ok1 = cv_pred(Xc, y, rng)
    pcb, ok2 = cv_pred(Xcb, y, rng)
    ok = ok1 & ok2
    ac, acb = auc(y[ok], pc[ok]), auc(y[ok], pcb[ok])
    d = []
    for _ in range(NBOOT):
        i = rng.integers(0, n, n)
        if 0 < y[i].sum() < n:
            try:
                d.append(auc(y[i], pcb[i]) - auc(y[i], pc[i]))
            except Exception:
                pass
    lo, hi = np.percentile(d, [2.5, 97.5]) if len(d) > 100 else (float("nan"),) * 2
    print(f"   category alone            CV AUC {ac:.3f}")
    print(f"   category + burden         CV AUC {acb:.3f}")
    print(f"   increment {acb-ac:+.3f} [{lo:+.3f},{hi:+.3f}]   (LPM gave +0.068; registered threshold +0.03)")
    b_full = logit_fit(Xcb, y)
    print(f"   burden log-odds coefficient {b_full[3]:+.3f}  -> odds ratio {np.exp(b_full[3]):.2f} "
          "per unit burden (0 to 1)")

    # ---- S2: calibration ---------------------------------------------------------------------------
    print("\n" + "=" * 92)
    print("S2  CALIBRATION -- is the predicted RISK right, not merely the ranking?")
    print("=" * 92)
    pp = np.clip(pcb[ok], 1e-6, 1 - 1e-6)
    yy = y[ok]
    lp = np.log(pp / (1 - pp))
    cal = logit_fit(np.column_stack([np.ones(len(lp)), lp]), yy)
    print(f"   calibration-in-the-large: mean predicted {pp.mean():.3f} vs observed {yy.mean():.3f}")
    print(f"   calibration intercept {cal[0]:+.3f} (ideal 0)   slope {cal[1]:.3f} (ideal 1)")
    print(f"\n   {'decile of predicted risk':26s} {'n':>6s} {'predicted':>11s} {'observed':>10s}")
    q = np.quantile(pp, np.linspace(0, 1, 11))
    for i in range(10):
        m = (pp >= q[i]) & (pp <= q[i + 1] if i == 9 else pp < q[i + 1])
        if m.sum() >= 10:
            print(f"   {i+1:<26d} {int(m.sum()):6d} {pp[m].mean():10.3f} {yy[m].mean():9.3f}")
    print("\n   A slope below 1 means predictions are too extreme; above 1, too conservative.")

    # ---- S3: morphology increment with a CI --------------------------------------------------------
    print("\n" + "=" * 92)
    print("S3  MORPHOLOGY INCREMENT, WITH THE CONFIDENCE INTERVAL IT NEVER HAD")
    print("=" * 92)
    hm = [r for r in g if r["cat"] == 2 and all(r[k] == r[k] for k in FEATS)]
    if len(hm) >= 150:
        yh = np.asarray([r["d3"] for r in hm], float)
        bh = np.asarray([r["bur"] for r in hm], float)
        M = np.column_stack([np.asarray([r[k] for r in hm], float) for k in FEATS])
        M = (M - M.mean(0)) / np.where(M.std(0) > 0, M.std(0), 1.0)
        A = np.column_stack([np.ones(len(hm)), bh])
        B = np.column_stack([A, M])
        pa, oka = cv_pred(A, yh, rng)
        pb, okb = cv_pred(B, yh, rng)
        o = oka & okb
        aa, ab = auc(yh[o], pa[o]), auc(yh[o], pb[o])
        dd = []
        for _ in range(NBOOT):
            i = rng.integers(0, len(hm), len(hm))
            if 0 < yh[i].sum() < len(i):
                try:
                    dd.append(auc(yh[i], pb[i]) - auc(yh[i], pa[i]))
                except Exception:
                    pass
        l2, h2 = np.percentile(dd, [2.5, 97.5]) if len(dd) > 100 else (float("nan"),) * 2
        print(f"   within highly malignant, n={len(hm):,}")
        print(f"   burden alone              CV AUC {aa:.3f}")
        print(f"   burden + morphology       CV AUC {ab:.3f}")
        print(f"   increment {ab-aa:+.3f} [{l2:+.3f},{h2:+.3f}]   "
              f"{'EXCLUDES ZERO' if l2 > 0 else 'INCLUDES ZERO -- weaker than previously reported'}")
    else:
        print(f"   only {len(hm)} with morphology; skipped")

    # ---- S4: clustering ----------------------------------------------------------------------------
    print("\n" + "=" * 92)
    print("S4  CLUSTERING")
    print("=" * 92)
    print(f"   rows {len(rows):,}   distinct patients {len({r['pid'] for r in rows}):,}")
    print("   The corrected analysis takes the INDEX recording only, so there is exactly one row per patient")
    print("   and no within-patient clustering to adjust for. The concern applies to the legacy")
    print("   max-over-recordings version, which is retained only for reproducing earlier runs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
