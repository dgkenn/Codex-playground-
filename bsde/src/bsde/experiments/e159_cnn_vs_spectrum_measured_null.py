#!/usr/bin/env python3
"""E159 -- E158's question with the leakage gate judged against the null it actually has.

REGISTERED BEFORE THE REPAIRED GATE HAS BEEN RUN. Successor to E158. The cohort, the alignment, the
leave-one-subject-out PCA, the candidate sets, the statistic and both directions are E158's, unchanged.
**One gate changes, and it changes because its null was measured rather than assumed.**

=========================================================================================================
WHAT E158 FOUND AND WHY IT COULD NOT ISSUE A VERDICT
=========================================================================================================
Out-of-fold AUC for `is_conscious`, subjects held out whole:

    CNN, 10 principal components (the paper's own reduction)   **0.8117**
    11 hand-built spectral features                            **0.9458**
    both                                                        0.9410

G1 alignment passed at **100.0 %** -- every one of the 46,948 CNN windows matches one of ours -- and G3
passed at p = 0.00000. **G2 failed**: with the label permuted within subject, the CNN components gave an
out-of-fold AUC of **0.4400** against a gate of [0.45, 0.55], which reads as a representation quietly
memorising something.

**It is not. The null is not centred on 0.5.** Measured directly over 50 within-subject permutations:

    CNN 10 PCs        mean **0.4463**, sd 0.0158, min 0.4187, max 0.4796
    spectral 11       mean **0.4486**, sd 0.0126, min 0.4231, max 0.4988

Two unrelated feature families, the same centre. **54 % of draws fall outside E158's nominal gate**, and
E158's single observed 0.4400 sits at the **36th percentile** of its own null -- entirely typical. The
bias comes from pooling within-subject and between-subject comparisons into one AUC while the folds hold
subjects out; it is a property of the design, not of either representation. This is now error-catalogue
rule 72, and its corollary governs how the numbers above may be read: **the pooled AUC LEVEL is biased
low, so the DIFFERENCE between two representations is the trustworthy quantity.**

=========================================================================================================
THE ONE CHANGE
=========================================================================================================
**G2 becomes a distribution test against the measured null.** Fifty within-subject permutations are run
for each representation, and the gate has two parts, both of which can fail:

  * the two families' permutation nulls must agree to within 0.02 in their means -- if a 1,280-column
    representation's null sits materially above an 11-column one's, that IS differential memorisation and
    the comparison is void;
  * **each representation's real AUC must exceed the maximum of its own 50-draw null.** That is a
    non-parametric bar with no assumed centre, and it is strictly harder than "beat 0.5" for a null
    centred at 0.4463 only when the real value is small -- which is the honest direction to be strict in.

Nothing else moves. In particular the primary is still the two permutation increments, which are immune
to the AUC's level bias because they compare a model against a permuted version of itself.

=========================================================================================================
PRIMARY -- WRONG-DIRECTION BRANCH FIRST (rule 37)
=========================================================================================================
**IF THE CNN ADDS TO THE SPECTRUM AND THE SPECTRUM DOES NOT ADD TO THE CNN**, then eleven interpretable
numbers are dominated by a learned representation of the same spectrogram and the programme should build
on the learned one. E158's raw AUCs point the other way by a wide margin, so this branch is unlikely --
which is exactly why it is written first, before the increments that decide it have been seen.

**REGISTERED PREDICTION: the spectrum adds to the CNN and the CNN adds little or nothing to the
spectrum**, unchanged from E158 and now supported by its AUCs, which is disclosed rather than presented
as independent.

SCOPE, unchanged and restated: ten subjects, propofol only, one label, and **the paper's stated reduction
to ten components fitted by ridge here** -- not necessarily the classifier the paper itself used. A
different reduction or a different learner could behave differently; this tests the published reduction,
not the best possible use of the bottlenecks.

WHAT WAS ALREADY SEEN (rule 41). All of E158's output including the three pooled AUCs, and the 50-draw
null measurements quoted above, which were run as a machinery diagnostic while the primary was still
executing and which touched no candidate-label relationship.

    python bsde/src/bsde/experiments/e159_cnn_vs_spectrum_measured_null.py
"""

from __future__ import annotations

import csv
import json
import math
import os
import sys
import warnings
from collections import defaultdict

import numpy as np

warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.verifier.stats import (auc, cluster_permute, grouped_cv_predict,     # noqa: E402
                                 permutation_increment)

sys.path.insert(0, HERE)
from e148_roc_concentration_matched_dissociation import FEATURES               # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e159_cnn_vs_spectrum.json")
FEATHER = os.path.join(RESULTS, "mgh_volunteer_cnn_btlncks.feather")
OURS = os.path.join(RESULTS, "mgh_volunteer_windows.csv")
E147_JSON = os.path.join(RESULTS, "e147_calibrated_increment.json")

N_PC = 10
PERMS = 300
NULL_DRAWS = 50
MEAN_AGREE = 0.02
FOLDS = 5


def neg_auc(t, p):
    t = np.asarray(t, float)
    p = np.asarray(p, float)
    ok = np.isfinite(p)
    if ok.sum() < 10 or len(set(t[ok].tolist())) < 2:
        return float("nan")
    return -auc(list(t[ok]), list(p[ok]))


def _f(s):
    try:
        v = float(s)
        return v if math.isfinite(v) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def load():
    import pyarrow.feather as pf
    tbl = pf.read_table(FEATHER)
    names = tbl.column_names
    bt = [c for c in names if c.startswith("btlnck_")]
    meta = {c: tbl.column(c).to_numpy(zero_copy_only=False) for c in
            ("case_id", "t", "is_conscious")}
    case = np.array([str(x) for x in meta["case_id"]])
    tt = np.round(np.asarray(meta["t"], float), 3)
    y = np.asarray(meta["is_conscious"]).astype(float)
    Z = np.column_stack([tbl.column(c).to_numpy(zero_copy_only=False) for c in bt]).astype(np.float32)

    ours = defaultdict(dict)
    for r in csv.DictReader(open(OURS, newline="")):
        ours[r["case"]][round(_f(r["t"]), 3)] = r
    S, keep = [], []
    for i in range(len(tt)):
        row = ours.get(case[i], {}).get(tt[i])
        if row is None:
            continue
        v = [_f(row[f]) for f in FEATURES]
        if not all(map(math.isfinite, v)):
            continue
        S.append(v)
        keep.append(i)
    keep = np.asarray(keep, int)
    return case[keep], tt[keep], y[keep], Z[keep], np.asarray(S, float), len(tt)


def loo_pcs(Z, subj, k=N_PC):
    """Leave-one-subject-out PCA scores. No held-out subject contributes to its own basis."""
    out = np.zeros((len(Z), k), float)
    for s in np.unique(subj):
        te = subj == s
        tr = ~te
        mu = Z[tr].mean(0)
        A = Z[tr] - mu
        # economical SVD on the covariance; 1,280 columns makes this cheap
        C = (A.T @ A) / max(len(A) - 1, 1)
        w, V = np.linalg.eigh(C.astype(np.float64))
        V = V[:, np.argsort(w)[::-1][:k]]
        out[te] = (Z[te] - mu) @ V
    return out


def main(argv=None) -> int:
    rng = np.random.default_rng(158)
    out = {"experiment": "E159", "n_pc": N_PC, "perms": PERMS, "null_draws": NULL_DRAWS}

    try:
        e147 = json.load(open(E147_JSON))
        g4 = bool(e147.get("G1", {}).get("pass"))
        print(f"G4 INSTRUMENT VALIDATION  E147 fpr={e147['G1']['fpr']:.4f} -> {'PASS' if g4 else 'FAIL'}")
    except Exception as e:                                                     # noqa: BLE001
        print(f"G4 INSTRUMENT VALIDATION  unreadable ({type(e).__name__}) -> FAIL")
        g4 = False
    if not g4:
        json.dump({**out, "G4": False}, open(OUT, "w"), indent=1, sort_keys=True)
        return 1

    case, tt, y, Z, S, n_cnn = load()
    frac = len(case) / n_cnn
    g1 = frac >= 0.95
    print(f"G1 ALIGNMENT  {len(case)} of {n_cnn} CNN windows matched our grid ({frac:.1%}) -> "
          f"{'PASS' if g1 else 'FAIL'}")
    print(f"   {len(np.unique(case))} subjects, label split "
          f"{int(y.sum())}/{int((1 - y).sum())}, {Z.shape[1]} bottleneck columns, "
          f"{S.shape[1]} spectral features")
    out["G1"] = {"pass": bool(g1), "matched": int(len(case)), "cnn_windows": int(n_cnn)}

    P = loo_pcs(Z, case)
    print(f"   leave-one-subject-out PCA -> {P.shape[1]} components")

    # ---- G2 leakage control, against the MEASURED null (rule 72) ---------------------------------------
    def perm_null(X, k=NULL_DRAWS):
        v = []
        for _ in range(k):
            yp = y.copy()
            for s in np.unique(case):
                m = case == s
                yp[m] = rng.permutation(yp[m])
            pr = grouped_cv_predict(X, yp, case, rng, folds=FOLDS)
            ok = np.isfinite(pr)
            v.append(auc(list(yp[ok]), list(pr[ok])))
        return np.sort(np.asarray(v, float))

    nP, nS = perm_null(P), perm_null(S)
    agree = abs(float(nP.mean()) - float(nS.mean()))
    print(f"G2 MEASURED NULL over {NULL_DRAWS} within-subject permutations")
    print(f"   CNN 10 PCs   mean {nP.mean():.4f} sd {nP.std(ddof=1):.4f} "
          f"[{nP.min():.4f}, {nP.max():.4f}]")
    print(f"   spectral 11  mean {nS.mean():.4f} sd {nS.std(ddof=1):.4f} "
          f"[{nS.min():.4f}, {nS.max():.4f}]")
    print(f"   family means agree to {agree:.4f} (bar {MEAN_AGREE}) -- a materially higher null for the "
          f"1,280-column representation would BE differential memorisation")
    out["G2_null"] = {"cnn": {"mean": float(nP.mean()), "sd": float(nP.std(ddof=1)),
                              "max": float(nP.max())},
                      "spectral": {"mean": float(nS.mean()), "sd": float(nS.std(ddof=1)),
                                   "max": float(nS.max())},
                      "mean_agreement": agree}

    # ---- headline out-of-fold AUCs ---------------------------------------------------------------------
    aucs = {}
    for tag, X in (("cnn_10pc", P), ("spectral_11", S), ("both", np.c_[P, S])):
        pr = grouped_cv_predict(X, y, case, rng, folds=FOLDS)
        m = np.isfinite(pr)
        aucs[tag] = auc(list(y[m]), list(pr[m]))
    print(f"\nOUT-OF-FOLD AUC for is_conscious, subjects held out whole")
    for k, v in aucs.items():
        print(f"   {k:14s} {v:.4f}")
    out["auc"] = aucs

    g2 = agree <= MEAN_AGREE and aucs["cnn_10pc"] > float(nP.max()) and \
        aucs["spectral_11"] > float(nS.max())
    print(f"G2 VERDICT  real AUCs must exceed their own null maxima "
          f"({nP.max():.4f} / {nS.max():.4f}) -> {'PASS' if g2 else 'FAIL'}")
    out["G2"] = {"pass": bool(g2)}

    # ---- G3 incumbent alive ----------------------------------------------------------------------------
    base = np.column_stack([cluster_permute(P[:, j], case, rng) for j in range(P.shape[1])])
    o, p, nm, k = permutation_increment(base, np.c_[base, P], y, case, rng, stat=neg_auc,
                                        reps=PERMS, n_extra=P.shape[1], folds=FOLDS)
    g3 = math.isfinite(p) and p < 0.05
    print(f"G3 INCUMBENT ALIVE  CNN components over a cluster-permuted copy: {o:+.5f} p={p:.5f} "
          f"-> {'PASS' if g3 else 'FAIL'}")
    out["G3"] = {"pass": bool(g3), "increment": o, "p": p}

    gates = g1 and g2 and g3
    print(f"\nGATES {'ALL PASS' if gates else 'NOT ALL PASSED -- no verdict is issued'}\n")

    # ---- both directions --------------------------------------------------------------------------------
    o1, p1, nm1, _ = permutation_increment(P, np.c_[P, S], y, case, rng, stat=neg_auc, reps=PERMS,
                                           n_extra=S.shape[1], folds=FOLDS)
    o2, p2, nm2, _ = permutation_increment(S, np.c_[S, P], y, case, rng, stat=neg_auc, reps=PERMS,
                                           n_extra=P.shape[1], folds=FOLDS)
    print(f"PRIMARY  (negative increment = the addition helps)")
    print(f"   spectrum added to the CNN : {o1:+.5f}  p={p1:.5f}  null_mean={nm1:+.5f}")
    print(f"   CNN added to the spectrum : {o2:+.5f}  p={p2:.5f}  null_mean={nm2:+.5f}")
    out["primary"] = {"spectrum_over_cnn": {"increment": o1, "p": p1},
                      "cnn_over_spectrum": {"increment": o2, "p": p2}}

    # ---- secondary: leave-one-feature-out --------------------------------------------------------------
    print(f"\nSECONDARY (no verdict) -- drop one spectral feature from the full model")
    drop = {}
    full = np.c_[P, S]
    pr = grouped_cv_predict(full, y, case, rng, folds=FOLDS)
    m = np.isfinite(pr)
    a_full = auc(list(y[m]), list(pr[m]))
    for j, f in enumerate(FEATURES):
        X = np.delete(full, P.shape[1] + j, axis=1)
        pr = grouped_cv_predict(X, y, case, rng, folds=FOLDS)
        m = np.isfinite(pr)
        drop[f] = a_full - auc(list(y[m]), list(pr[m]))
    for f in sorted(drop, key=lambda x: -drop[x]):
        print(f"   {f:18s} AUC lost when dropped: {drop[f]:+.5f}")
    out["leave_one_out"] = drop
    out["auc_full"] = a_full

    if not gates:
        verdict = "NO VERDICT -- a gate failed"
    elif p1 < 0.05 and not (p2 < 0.05):
        verdict = (f"THE SPECTRUM WINS -- eleven hand-built numbers add to the published CNN "
                   f"representation (p={p1:.4f}) and the CNN does not add to them (p={p2:.4f}). "
                   f"Out-of-fold AUC: CNN {aucs['cnn_10pc']:.4f}, spectral {aucs['spectral_11']:.4f}, "
                   f"both {aucs['both']:.4f}. Registered prediction confirmed.")
    elif p2 < 0.05 and not (p1 < 0.05):
        verdict = (f"THE CNN WINS -- the published learned representation adds to the spectral panel "
                   f"(p={p2:.4f}) and the panel does not add to it (p={p1:.4f}). Eleven interpretable "
                   f"numbers are dominated by a learned representation of the same spectrogram, the "
                   f"registered prediction is WRONG, and the programme should build on the learned "
                   f"representation rather than add more hand-built features.")
    elif p1 < 0.05 and p2 < 0.05:
        verdict = (f"BOTH ADD -- each representation carries information the other does not "
                   f"(spectrum over CNN p={p1:.4f}, CNN over spectrum p={p2:.4f}). Neither dominates, "
                   f"and the honest reading is that the learned reduction and the interpretable panel "
                   f"are complementary at these ten subjects.")
    else:
        verdict = (f"NEITHER ADDS -- p={p1:.4f} and p={p2:.4f}. At ten subjects the two representations "
                   f"are not distinguishable from one another by this test, which is a statement about "
                   f"the cohort's size and not about either representation.")
    print(f"\nVERDICT: {verdict}")
    out["verdict"] = verdict
    json.dump(out, open(OUT, "w"), indent=1, sort_keys=True, allow_nan=True)
    print(f"\n   wrote {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
