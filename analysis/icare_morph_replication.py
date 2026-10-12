#!/usr/bin/env python3
"""Does the burst-morphology signature replicate, with the directions fixed in advance?

PRE-REGISTERED FROM HEEDB. These are the observed contrasts between patients dead within three days and those
alive past 180 days, and they are the predictions -- not hypotheses generated after seeing I-CARE:

    burst duration        1.84 s  (dead)   vs  2.87 s  (survived)   -> SURVIVORS' BURSTS ARE LONGER
    intra-burst 8-30 Hz   0.250   (dead)   vs  0.120   (survived)   -> SURVIVORS' BURSTS ARE SLOWER
    suppression burden    0.746   (dead)   vs  0.386   (survived)   -> more suppression is worse

MECHANISM UNDER TEST: thalamocortical generator integrity. Long, slow, organised bursts require an intact
thalamocortical loop; short fast fragments can be produced by cortex alone. Burden counts how much generator
capacity is gone; morphology reports whether what remains is still organised.

  M1  DIRECTION. In I-CARE, poor-outcome patients have SHORTER bursts and MORE high-frequency intra-burst
      content. FALSIFIED IF either direction inverts.
  M2  INCREMENT. Morphology adds cross-validated discrimination over burden alone. HEEDB gave
      +0.047 [+0.011, +0.083].
  M3  INDEPENDENCE. The morphology effect survives adjustment for burden -- i.e. it is not a restatement of
      how suppressed the record is. This is the arm that decides whether "quality" is separable from
      "quantity", which is the whole content of the mechanism.

WHAT WOULD KILL THE CANDIDATE: inverted directions, or a morphology effect that vanishes once burden is
adjusted for. Either would mean morphology is a proxy for depth of suppression rather than a marker of
generator organisation.
"""
import csv, os, sys

import numpy as np

COHORT = os.environ.get("ICARE_COHORT", "/tmp/eeg_probe/icare_cohort.csv")
# Default points at the extraction that actually carries the stereotypy columns. The earlier default
# (icare_morph.csv) predates them, and because the row loop swallows KeyError it would have silently filtered
# every row and reported "extraction still running or too sparse" instead of failing -- a silent-empty trap of
# exactly the kind that has already cost this project once.
MORPH = os.environ.get("ICARE_MORPH_OUT", "/tmp/eeg_probe/icare_morph2.csv")
NBOOT = int(os.environ.get("NBOOT", "600"))
# stereotypy_2s added because Fong et al. (Neurocrit Care 2025, PMID 39900751) found the burst correlation
# coefficient over the first 2 s to be the ONLY independent EEG predictor of mortality in 203 post-arrest
# patients -- the direct competitor to our spectral-content claim, and absent from our first extraction.
FEATS = ("burst_dur", "alpha_beta", "burst_amp", "burst_rate", "stereotypy_1s", "stereotypy_2s")


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


def oob_increment(Xa, Xb, y, rng, reps=300):
    """Out-of-bag bootstrap for the AUC increment: train on the resampled patients, evaluate on those NOT
    drawn. Refitting on a resample and evaluating on that same resample puts a patient in train and test and
    inflates AUC; bootstrapping fixed out-of-fold predictions ignores refit variance. Both were used earlier
    in this project and both were wrong."""
    n = len(y)
    out = []
    for _ in range(reps):
        tr = rng.integers(0, n, n)
        oob = np.setdiff1d(np.arange(n), np.unique(tr))
        if len(oob) < 30 or y[tr].sum() < 10 or (n - y[tr].sum()) < 10:
            continue
        if y[oob].sum() < 5 or (len(oob) - y[oob].sum()) < 5:
            continue
        try:
            aa = auc(y[oob], predict(Xa[oob], logit_fit(Xa[tr], y[tr])))
            ab = auc(y[oob], predict(Xb[oob], logit_fit(Xb[tr], y[tr])))
            if aa == aa and ab == ab:
                out.append(ab - aa)
        except Exception:
            continue
    if len(out) < 30:
        return float("nan"), float("nan"), float("nan"), 0
    a = np.asarray(out, float)
    lo, hi = np.percentile(a, [2.5, 97.5])
    return float(a.mean()), float(lo), float(hi), len(a)


def main():
    rng = np.random.default_rng(20260726)
    if not os.path.exists(MORPH):
        print(f"missing {MORPH} -- run analysis/icare_burst_morphology.py")
        return 1

    coh = {}
    for r in csv.DictReader(open(COHORT)):
        pid = (r.get("pid") or "").strip()
        try:
            cpc = float(r.get("cpc"))
        except Exception:
            continue
        if pid and cpc == cpc:
            coh[pid] = 1.0 if cpc >= 3 else 0.0

    rows = []
    n_bad = n_nan = 0
    for r in csv.DictReader(open(MORPH)):
        pid = (r.get("pid") or "").strip()
        if pid not in coh:
            continue
        try:
            d = {k: float(r[k]) for k in FEATS}
            d["burden"] = float(r["burden"])
            d["nb"] = float(r["n_bursts"])
        except KeyError as e:
            raise SystemExit(f"{MORPH} lacks column {e}; it predates the stereotypy/BSP extraction. "
                             f"Set ICARE_MORPH_OUT to a file produced by the current "
                             f"analysis/icare_burst_morphology.py") from None
        except Exception:
            n_bad += 1
            continue
        if any(v != v for v in d.values()):
            n_nan += 1
            continue
        d["y"] = coh[pid]; d["pid"] = pid
        rows.append(d)
    n = len(rows)
    print(f"I-CARE patients with burst morphology and an outcome: {n:,}")
    # Report the exclusions rather than letting them pass silently: they are NOT outcome-neutral. Morphology
    # is undefined below four bursts, which happens exactly when suppression is near-total, so the excluded
    # patients sit at the top of the burden axis and have far worse outcomes.
    print(f"   EXCLUDED: {n_nan} with a non-computable feature, {n_bad} unparsable. Morphology cannot be")
    print(f"   measured in a record with almost no bursts, so these are not missing at random -- in I-CARE the")
    print(f"   excluded are ~80% poor outcome against ~60% retained. Every morphology result below is")
    print(f"   conditioned on the EEG containing at least four identifiable bursts.")
    if n < 120:
        print("*** extraction still running or too sparse; rerun when it completes")
        return 1
    y = np.array([r["y"] for r in rows], float)
    print(f"   poor outcome (CPC 3-5): {int(y.sum()):,} ({100*y.mean():.1f}%)")

    # ---- M1: direction ------------------------------------------------------------------------------
    print("\n" + "=" * 92)
    print("M1  DIRECTION -- do the HEEDB contrasts reproduce?")
    print("=" * 92)
    print(f"   {'feature':16s} {'poor':>10s} {'good':>10s} {'diff':>10s} {'HEEDB direction':>18s} {'':>10s}")
    heedb = {"burst_dur": ("longer in survivors", -1), "alpha_beta": ("faster in deaths", +1),
             "burden": ("higher in deaths", +1), "burst_amp": ("(exploratory)", 0),
             "burst_rate": ("(exploratory)", 0),
             # Fong 2025 predicts MORE similar bursts in those who die (aOR 4.82 over 2 s)
             "stereotypy_1s": ("Fong: higher in deaths", +1),
             "stereotypy_2s": ("Fong: higher in deaths", +1)}
    verdict = {}
    for k in ("burden",) + FEATS:
        a = np.array([r[k] for r in rows if r["y"] == 1.0])
        b = np.array([r[k] for r in rows if r["y"] == 0.0])
        if len(a) < 10 or len(b) < 10:
            continue
        diff = float(a.mean() - b.mean())
        d = []
        for _ in range(NBOOT):
            i = rng.integers(0, n, n)
            aa = np.array([rows[j][k] for j in i if rows[j]["y"] == 1.0])
            bb = np.array([rows[j][k] for j in i if rows[j]["y"] == 0.0])
            if len(aa) >= 5 and len(bb) >= 5:
                d.append(float(aa.mean() - bb.mean()))
        lo, hi = np.percentile(d, [2.5, 97.5]) if len(d) > 100 else (float("nan"),) * 2
        lab, exp = heedb.get(k, ("", 0))
        ok = ""
        if exp != 0:
            got = 1 if lo > 0 else (-1 if hi < 0 else 0)
            ok = "REPLICATES" if got == exp else ("INVERTS" if got == -exp else "n.s.")
            verdict[k] = ok
        print(f"   {k:16s} {a.mean():10.3f} {b.mean():10.3f} {diff:+10.3f} {lab:>18s} {ok:>10s}")

    # ---- M2 / M3 ------------------------------------------------------------------------------------
    print("\n" + "=" * 92)
    print("M2/M3  DOES MORPHOLOGY ADD OVER BURDEN, AND SURVIVE ADJUSTMENT FOR IT?")
    print("=" * 92)
    one = np.ones(n)
    bur = np.array([r["burden"] for r in rows], float)
    M = np.column_stack([np.array([r[k] for r in rows], float) for k in FEATS])
    M = (M - M.mean(0)) / np.where(M.std(0) > 0, M.std(0), 1.0)
    A = np.column_stack([one, bur])
    B = np.column_stack([A, M])
    ca, cb = cv_auc(A, y, rng), cv_auc(B, y, rng)
    inc, lo, hi, nrep = oob_increment(A, B, y, rng)
    print(f"   burden alone            CV AUC {ca:.3f}   (5x5 repeated CV, for reference)")
    print(f"   burden + morphology     CV AUC {cb:.3f}")
    print(f"   INCREMENT, out-of-bag bootstrap ({nrep} replicates): {inc:+.3f} [{lo:+.3f},{hi:+.3f}]")
    print(f"   HEEDB under the same estimator: +0.036 [-0.019, +0.076] -- includes zero")
    print(f"   M2 {'REPLICATES' if lo > 0 else 'DOES NOT REACH SIGNIFICANCE'}")

    print("\n   M3  coefficients WITH burden in the model (standardised, log-odds):")
    bfull = logit_fit(B, y)
    for j, k in enumerate(FEATS):
        col = 2 + j
        bs = []
        for _ in range(NBOOT):
            i = rng.integers(0, n, n)
            if 0 < y[i].sum() < n:
                try:
                    bs.append(float(logit_fit(B[i], y[i])[col]))
                except Exception:
                    continue
        l2, h2 = np.percentile(bs, [2.5, 97.5]) if len(bs) > 100 else (float("nan"),) * 2
        sig = "*" if (l2 > 0 or h2 < 0) else " "
        print(f"      {k:14s} {bfull[col]:+7.3f} [{l2:+.3f},{h2:+.3f}] {sig}")
    print(f"      {'burden':14s} {bfull[1]:+7.3f}")
    print("\n   M3 asks whether burst QUALITY is separable from suppression QUANTITY. If the morphology")
    print("   coefficients collapse to zero once burden is in the model, morphology is a restatement of")
    print("   depth and the generator-integrity reading is unsupported.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
