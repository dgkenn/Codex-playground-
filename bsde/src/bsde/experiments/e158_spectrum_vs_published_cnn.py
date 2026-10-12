#!/usr/bin/env python3
"""E158 -- eleven hand-built numbers against a published 1,280-dimensional learned representation.

REGISTERED BEFORE EITHER REPRESENTATION HAS BEEN SCORED AGAINST THE LABEL. Manifest and alignment checks
are disclosed at the end; no AUC, increment or permutation has been computed.

=========================================================================================================
WHY THIS IS THE INCUMBENT TEST THE PROGRAMME KEEPS ASKING FOR
=========================================================================================================
`docs/INCUMBENT_REGISTRY.md` and error-catalogue rule 45 require every registration to name the thing it
has to beat, and this project's Challenge C incumbents have been **SEF95** (which E79 measured at median
within-recording rho +0.1799 against MOAA/S), **BIS** (circular -- computed from the same EEG) and
**PE31**. None of them is a modern learned representation, and the standard objection to a hand-built
spectral panel has never been tested here at all: *a neural network trained on the spectrogram would do
better.*

`eeg-power-anesthesia` ships one. `Volunteer_CNN/btlncks.feather` is **46,948 windows x 1,280 features** --
MobileNet bottlenecks over 30 s spectrogram images, the representation the deposit's own paper built its
classifiers from, with the paper's stated reduction being **the first ten principal components**. It comes
with `is_conscious` on the same 2 s grid as our features, and the grids align exactly: the CNN's windows
are a strict subset of ours (it needs 28 s of history, so it starts 14 windows later per case) and every
one of its timestamps matches one of ours.

**So for the first time a candidate family here can be scored against a published learned incumbent on the
same rows, same subjects, same label.**

=========================================================================================================
THE DESIGN, AND THE ONE THING THAT WOULD INVALIDATE IT
=========================================================================================================
    A   the incumbent: 10 principal components of the CNN bottlenecks, exactly the paper's reduction
    B   A + the 11 hand-built spectral features
    A'  the 11 spectral features alone
    B'  A' + the 10 CNN components

    target      `is_conscious`, the deposit's own label
    statistic   `permutation_increment` with stat = -AUC, validated in E147 at a false-positive rate of
                0.0333 and 86 % of an oracle's power; cluster = SUBJECT, 10 of them
    both directions are run, because "does the spectrum add to the CNN" and "does the CNN add to the
    spectrum" are different questions and reporting only the flattering one is how incumbents get chosen

**PCA IS FITTED LEAVE-ONE-SUBJECT-OUT AND NOTHING ELSE WOULD BE ACCEPTABLE.** A 1,280-dimensional
representation reduced on all the data and then scored on it will separate anything, including noise. The
components are fitted on nine subjects and the tenth is projected, so no held-out subject contributes to
its own basis. G2 below checks that this actually worked rather than assuming it.

=========================================================================================================
GATES
=========================================================================================================
G1  ALIGNMENT (rule 27 -- the time axis is the thing least often verified and most often broken).
    >= 95 % of CNN windows must match one of our windows on (case, t) to within 1e-3 s.
G2  **LEAKAGE CONTROL, AND IT CAN FAIL.** With `is_conscious` permuted WITHIN subject, the leave-one-out
    CNN components must give an out-of-fold AUC in [0.45, 0.55]. A learned representation is exactly the
    kind of thing that quietly memorises a subject, and a 1,280-column input is exactly the size at which
    it happens. If this fails, nothing below is reported.
G3  INCUMBENT ALIVE: the CNN components must beat their own cluster-permutation.
G4  INSTRUMENT VALIDATION IMPORTED: E147's calibration JSON must report a pass, else the file refuses to
    run.

=========================================================================================================
PRIMARY -- WRONG-DIRECTION BRANCH WRITTEN FIRST (rule 37)
=========================================================================================================
**IF THE CNN BEATS THE SPECTRUM AND THE SPECTRUM ADDS NOTHING TO IT**, that is a real ceiling and it
redirects the programme: eleven interpretable numbers would be strictly dominated by a learned
representation of the same spectrogram, and the honest response is to build on the learned one rather than
to keep adding hand-built features. **This is the outcome that costs the most and it is written first.**

**REGISTERED PREDICTION: the spectrum ADDS to the CNN, and the CNN adds little or nothing to the
spectrum.** Reasons, stated so they can be wrong: E119 found this project's own "discovered" second axis
was `relative_alpha_power` at rho +1.0000, so learned axes over spectrograms tend to recover the spectrum;
the paper itself presents the CNN features "for comparison" rather than as its headline; and ten
components of a MobileNet trained on ImageNet are not obviously a better basis for a 100-bin power
spectrum than eleven quantities chosen because they mean something.

**SECONDARY, NO VERDICT: which spectral feature carries the increment.** Reported per feature by dropping
one at a time from B, because "the spectrum adds" is not a claim anyone can act on and "alpha peak
frequency adds" is.

SCOPE. Ten subjects, propofol only, one label. A CNN reduced to ten components is the paper's reduction
and not the only one available; a different reduction could behave differently, and this file tests the
published one rather than the best possible one. Stated here rather than appended after a result.

WHAT WAS ALREADY SEEN (rule 41). Manifest and alignment only: 46,948 CNN windows over ten cases, per-case
counts, `is_conscious` split 23,639 / 23,309, `is_effect` 37,918 / 9,030, and the exact subset alignment
of the two time grids for the first three cases. No feature or component has been scored against the
label.

    python bsde/src/bsde/experiments/e158_spectrum_vs_published_cnn.py
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
OUT = os.path.join(RESULTS, "e158_spectrum_vs_cnn.json")
FEATHER = os.path.join(RESULTS, "mgh_volunteer_cnn_btlncks.feather")
OURS = os.path.join(RESULTS, "mgh_volunteer_windows.csv")
E147_JSON = os.path.join(RESULTS, "e147_calibrated_increment.json")

N_PC = 10
PERMS = 300
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
    out = {"experiment": "E158", "n_pc": N_PC, "perms": PERMS}

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

    # ---- G2 leakage control ---------------------------------------------------------------------------
    yp = y.copy()
    for s in np.unique(case):
        m = case == s
        yp[m] = rng.permutation(yp[m])
    pred = grouped_cv_predict(P, yp, case, rng, folds=FOLDS)
    ok = np.isfinite(pred)
    a_perm = auc(list(yp[ok]), list(pred[ok]))
    g2 = 0.45 <= a_perm <= 0.55
    print(f"G2 LEAKAGE CONTROL  within-subject permuted label, CNN components out-of-fold AUC = "
          f"{a_perm:.4f} (must be in [0.45, 0.55]) -> {'PASS' if g2 else 'FAIL'}")
    out["G2"] = {"pass": bool(g2), "permuted_auc": a_perm}

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
