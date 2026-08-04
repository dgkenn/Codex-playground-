#!/usr/bin/env python3
"""EXTERNAL REPLICATION of the core claim, in an independent international consortium.

WHY NOT TUH, WHICH THE PRE-REGISTRATION NAMES. The TUH EEG Corpus is EEG recordings plus de-identified clinical
reports and carries **no linked outcome data**; this repository's own TUH manifest schema in `config.yaml`
lists `recording_id, patient_id, edf_path, sfreq, age, sex` and no outcome field. Our finding is
burden -> near-term death, so it cannot be replicated there at any effort. TUH remains the right target for
replicating the MEASUREMENT (agreement of burden with a clinician label at a different health system), which is
a different and lesser claim, and needs NEDC credentials that are not present.

WHY I-CARE IS THE RIGHT TARGET INSTEAD. The International Cardiac Arrest REsearch consortium cohort is the same
POPULATION as ours -- comatose patients after cardiac arrest -- recorded at five hospitals in a different
consortium, with different equipment, different clinicians and different health systems, and it carries a real
outcome (Cerebral Performance Category). That is a stronger external test than a same-network second hospital,
which is all the main analysis has.

WHAT IS BEING REPLICATED, precisely. The core claim is NOT "suppression is bad" -- everyone knows that. It is:

    **Among patients who ARE suppressed, the QUANTITATIVE burden still stratifies outcome, so the categorical
    label discards real information.**

  E1  Across all patients, poor outcome rises monotonically across quintiles of suppression burden.
  E2  THE ONE THAT MATTERS. Restricted to patients who ARE suppressed -- the analogue of the guideline's
      "highly malignant" tier -- burden still stratifies outcome. This is the claim that makes the finding
      more than a restatement of the category.
  E3  Burden adds cross-validated discrimination OVER a binary suppression flag, by at least +0.03 AUC, which
      is the same pre-registered threshold used in the main analysis.
  E4  CROSS-HOSPITAL: fit at one hospital, evaluate at the others.

WHAT DIFFERS FROM THE PRIMARY ANALYSIS, and must be said. The outcome here is CPC (poor = CPC 3-5), a
neurological outcome assessed at discharge or follow-up, NOT time-to-death within three days. The suppression
measure is this cohort's own, computed at hour 24 after arrest rather than at an index clinical recording. So
this replicates the STRUCTURE of the claim -- quantitative burden stratifies within the suppressed -- on an
independent cohort, not the identical estimand.
"""
import csv, os, sys
from collections import defaultdict

import numpy as np

COHORT = os.environ.get("ICARE_COHORT", "/tmp/eeg_probe/icare_cohort.csv")
BS = os.environ.get("ICARE_BS", "/tmp/eeg_probe/icare_bs.csv")
NBOOT = int(os.environ.get("NBOOT", "600"))


def logit_fit(X, y, iters=60, ridge=1e-6):
    b = np.zeros(X.shape[1])
    for _ in range(iters):
        eta = np.clip(X @ b, -30, 30)
        p = 1.0 / (1.0 + np.exp(-eta))
        w = np.clip(p * (1 - p), 1e-9, None)
        z = eta + (y - p) / w
        A = X.T @ (X * w[:, None]) + ridge * np.eye(X.shape[1])
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


def cv_auc(X, y, rng, folds=5, reps=5):
    out = []
    for _ in range(reps):
        idx = rng.permutation(len(y))
        for f in range(folds):
            te = idx[f::folds]; tr = np.setdiff1d(idx, te)
            if y[tr].sum() < 5 or (len(tr) - y[tr].sum()) < 5 or y[te].sum() < 2:
                continue
            try:
                out.append(auc(y[te], predict(X[te], logit_fit(X[tr], y[tr]))))
            except Exception:
                continue
    return float(np.nanmean(out)) if out else float("nan")


def main():
    rng = np.random.default_rng(20260726)

    coh = {}
    with open(COHORT) as fh:
        for r in csv.DictReader(fh):
            pid = (r.get("pid") or "").strip()
            if not pid:
                continue
            try:
                cpc = float(r.get("cpc"))
            except Exception:
                continue
            if not (cpc == cpc):
                continue
            coh[pid] = dict(hosp=(r.get("hospital") or "?").strip(), cpc=cpc,
                            poor=1.0 if cpc >= 3 else 0.0,
                            outcome=(r.get("outcome") or "").strip())

    bs = {}
    with open(BS) as fh:
        for r in csv.DictReader(fh):
            pid = (r.get("pid") or "").strip()
            try:
                v = float(r.get("bs")); vm = float(r.get("bs_max"))
            except Exception:
                continue
            if v == v:
                bs[pid] = (v, vm)

    rows = []
    for pid, c in coh.items():
        if pid in bs:
            rows.append(dict(pid=pid, hosp=c["hosp"], poor=c["poor"], cpc=c["cpc"],
                             bur=bs[pid][0], burmax=bs[pid][1]))
    n = len(rows)
    print(f"I-CARE patients with outcome and a suppression measure: {n:,}")
    if n < 150:
        print("*** insufficient")
        return 1
    hs = defaultdict(int)
    for r in rows:
        hs[r["hosp"]] += 1
    print(f"   hospitals: {dict(sorted(hs.items()))}")
    y = np.array([r["poor"] for r in rows], float)
    b = np.array([r["bur"] for r in rows], float)
    print(f"   poor outcome (CPC 3-5): {int(y.sum()):,} ({100*y.mean():.1f}%)")
    print(f"   suppression burden: median {np.median(b):.3f}  IQR "
          f"{np.percentile(b,25):.3f}-{np.percentile(b,75):.3f}")

    # ---- E1 ----------------------------------------------------------------------------------------
    print("\n" + "=" * 92)
    print("E1  DOES POOR OUTCOME RISE ACROSS BURDEN QUINTILES?  (all patients)")
    print("=" * 92)
    q = np.percentile(b, [20, 40, 60, 80])
    edges = [(-1e9, q[0]), (q[0], q[1]), (q[1], q[2]), (q[2], q[3]), (q[3], 1e9)]
    rates = []
    print(f"   {'quintile':14s} {'n':>6s} {'poor outcome':>14s}")
    for i, (lo, hi) in enumerate(edges):
        m = (b > lo) & (b <= hi)
        if m.sum() >= 5:
            rates.append(float(y[m].mean()))
            print(f"   Q{i+1:<13d} {int(m.sum()):6d} {100*y[m].mean():13.1f}%")
    mono = all(rates[i] <= rates[i + 1] + 1e-9 for i in range(len(rates) - 1))
    print(f"   monotone: {mono}")

    # ---- E2: the claim that matters ---------------------------------------------------------------
    print("\n" + "=" * 92)
    print("E2  AMONG THE SUPPRESSED, DOES QUANTITATIVE BURDEN STILL STRATIFY?")
    print("=" * 92)
    print("   (the analogue of asking whether the guideline's highly-malignant tier is homogeneous)")
    for thr in (0.05, 0.10, 0.20):
        g = [r for r in rows if r["bur"] >= thr]
        if len(g) < 80:
            print(f"   suppressed (burden >= {thr:.2f}): n={len(g)} -- too few")
            continue
        gy = np.array([r["poor"] for r in g], float)
        gb = np.array([r["bur"] for r in g], float)
        if gy.min() == gy.max():
            print(f"   suppressed (burden >= {thr:.2f}): n={len(g)}, outcome has no variance")
            continue
        tq = np.percentile(gb, [33, 67])
        lo_g = gy[gb <= tq[0]]; hi_g = gy[gb > tq[1]]
        d = []
        for _ in range(NBOOT):
            i = rng.integers(0, len(g), len(g))
            yy, bb = gy[i], gb[i]
            t2 = np.percentile(bb, [33, 67])
            l2, h2 = yy[bb <= t2[0]], yy[bb > t2[1]]
            if len(l2) >= 10 and len(h2) >= 10:
                d.append(float(h2.mean() - l2.mean()))
        lo_c, hi_c = np.percentile(d, [2.5, 97.5]) if len(d) > 100 else (float("nan"),) * 2
        print(f"\n   suppressed (burden >= {thr:.2f}): n={len(g):,}, poor {100*gy.mean():.1f}%")
        print(f"      lowest tertile  n={len(lo_g):4d}  poor {100*lo_g.mean():5.1f}%")
        print(f"      highest tertile n={len(hi_g):4d}  poor {100*hi_g.mean():5.1f}%")
        print(f"      difference {100*(hi_g.mean()-lo_g.mean()):+.1f} pp [{100*lo_c:+.1f},{100*hi_c:+.1f}]  "
              f"{'REPLICATES' if lo_c > 0 else 'does not reach significance'}")

    # ---- E3 ----------------------------------------------------------------------------------------
    print("\n" + "=" * 92)
    print("E3  DOES CONTINUOUS BURDEN ADD OVER A BINARY SUPPRESSION FLAG?")
    print("=" * 92)
    one = np.ones(n)
    for thr in (0.05, 0.10):
        flag = (b >= thr).astype(float)
        Xf = np.column_stack([one, flag])
        Xfb = np.column_stack([one, flag, b])
        cf, cfb = cv_auc(Xf, y, rng), cv_auc(Xfb, y, rng)
        pf, ok = np.full(n, np.nan), None
        d = []
        # bootstrap the increment using out-of-fold predictions from each resample's own fit
        for _ in range(200):
            i = rng.integers(0, n, n)
            if y[i].sum() < 10 or (n - y[i].sum()) < 10:
                continue
            try:
                a1 = cv_auc(Xf[i], y[i], rng, folds=5, reps=1)
                a2 = cv_auc(Xfb[i], y[i], rng, folds=5, reps=1)
                if a1 == a1 and a2 == a2:
                    d.append(a2 - a1)
            except Exception:
                continue
        lo_c, hi_c = np.percentile(d, [2.5, 97.5]) if len(d) > 50 else (float("nan"),) * 2
        print(f"   threshold {thr:.2f}:  flag alone {cf:.3f}   flag + burden {cfb:.3f}   "
              f"increment {cfb-cf:+.3f} [{lo_c:+.3f},{hi_c:+.3f}]")
    print("   registered threshold in the primary analysis was +0.03")

    # ---- E4: cross-hospital ------------------------------------------------------------------------
    print("\n" + "=" * 92)
    print("E4  CROSS-HOSPITAL -- fit at one site, evaluate at the others")
    print("=" * 92)
    print(f"   {'train site':12s} {'n train':>8s} {'n test':>8s} {'AUC at the other sites':>24s}")
    for h in sorted(hs):
        tr = [r for r in rows if r["hosp"] == h]
        te = [r for r in rows if r["hosp"] != h]
        if len(tr) < 60 or len(te) < 60:
            continue
        ytr = np.array([r["poor"] for r in tr], float)
        yte = np.array([r["poor"] for r in te], float)
        if ytr.min() == ytr.max() or yte.min() == yte.max():
            continue
        Xtr = np.column_stack([np.ones(len(tr)), [r["bur"] for r in tr]])
        Xte = np.column_stack([np.ones(len(te)), [r["bur"] for r in te]])
        a = auc(yte, predict(Xte, logit_fit(Xtr, ytr)))
        print(f"   {h:12s} {len(tr):8d} {len(te):8d} {a:23.3f}")
    print("\n   The primary analysis achieved 0.679 / 0.669 across two hospitals of ONE health system.")
    print("   These sites are independent institutions in a different consortium.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
