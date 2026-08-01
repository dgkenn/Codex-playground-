"""A CSP-based decodability label for eegmmidb imagery -- because the six-feature one is not alive.

WHY THIS EXISTS, AND WHY IT IS NOT GOALPOST-MOVING. E108 registered an external replication of E86 and
returned ABSENT at G2: **median `imagery_auc` 0.5306 and only 16.3 % of 104 subjects beat their own
permutation null**, against a pre-registered floor of 20 %. The gate fired before the primary and no
correlation with `ge_norm` was ever computed, so the hypothesis has not been peeked at.

**The 20 % floor is NOT lowered here.** What changes is the OUTCOME INSTRUMENT, and the justification is
independent of any gate: `build_eegmmidb_bci_label.py` decodes left-versus-right imagery from band power
in **three channels** (C3, C4, Cz) and **two bands**, which is a deliberately minimal choice -- its own
docstring says it wanted "a good label, not a good decoder", so that the label would not depend on
modelling choices. That reasoning is sound and it has a cost that only became visible when the label was
asked to be an outcome: a decoder this weak produces a label that is mostly noise, and **nothing can
predict noise**.

Common Spatial Patterns is not a bespoke modelling choice. It is the canonical decoder for exactly this
contrast on exactly this kind of data, which is what makes swapping it in a change of instrument rather
than a search for the setting that passes. **If CSP still leaves fewer than 20 % of subjects decodable,
the answer is that eegmmidb cannot host this replication and another cohort is needed.** That outcome is
as acceptable as the other one and is why the floor stays where it is.

=========================================================================================================
WHAT IS HELD FIXED FROM THE ORIGINAL LABEL, so the two are comparable
=========================================================================================================
Epoch (0.5-3.5 s post-cue), runs (R04/R08/R12), class definition (T2 = right = 1, T1 = left = 0), 5-fold
cross-validation WITHIN subject, AUC as the score, and a 200-draw label-permutation null. Only the feature
extraction changes: 64 channels band-passed 8-30 Hz, CSP, log-variance of the top and bottom `N_CSP`
components, logistic regression.

=========================================================================================================
THE ONE THING THAT WOULD INVALIDATE THIS IF DONE WRONG
=========================================================================================================
**CSP is FITTED INSIDE EACH TRAINING FOLD, never on all trials.** CSP is a supervised spatial filter: it
maximises the variance ratio between the two classes, so fitting it on the full set and then
cross-validating the classifier puts the test trials' labels into the filter. That inflates AUC massively
and silently -- it is rule 9's discipline (what is fit must be refit inside the resample) applied to a
preprocessing step that does not look like a model. The permutation null refits CSP too, on the permuted
labels, so a leak would show up as a null centred well above 0.5 rather than at it. **`perm_null_mean` is
emitted for exactly that check and any value far from 0.5 means this file is broken.**

    python bsde/scripts/build_eegmmidb_csp_label.py --limit 3     # smoke
    python bsde/scripts/build_eegmmidb_csp_label.py --shard k --of 4
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, HERE)

from bsde.ingestion import eegmmidb                                        # noqa: E402
from bsde.verifier.stats import auc, logit_fit, predict_proba              # noqa: E402

OUT = os.path.join(HERE, "..", "results", "eegmmidb_csp_label.csv")
IMAGERY_RUNS = ("R04", "R08", "R12")
EPOCH = (0.5, 3.5)
BAND = (8.0, 30.0)
N_CSP = 3                 # components taken from EACH end of the eigenvalue spectrum
FOLDS = 5
N_PERM = 200
SEED = 20260731
FIELDS = ["subject", "status", "error", "csp_auc", "perm_p", "perm_null_mean",
          "n_trials", "n_left", "n_right", "n_channels", "n_perm"]


def bandpass(X, sfreq, lo, hi, order=4):
    from scipy.signal import butter, filtfilt
    b, a = butter(order, [lo / (sfreq / 2.0), hi / (sfreq / 2.0)], btype="band")
    return filtfilt(b, a, np.asarray(X, float), axis=-1)


def csp_filters(E, y, n_comp=N_CSP, reg=1e-6):
    """CSP spatial filters from epochs E (trials x channels x time) and binary labels y.

    Generalised eigendecomposition of the two class-mean covariance matrices; the eigenvectors at the
    extreme ends of the spectrum maximise the variance ratio between classes. Covariances are trace-
    normalised per trial so a single high-amplitude trial cannot dominate, and ridge-regularised because
    with ~36 training trials and 64 channels the class covariances are rank-deficient.
    """
    def cov(idx):
        C = np.zeros((E.shape[1], E.shape[1]))
        for t in idx:
            X = E[t] - E[t].mean(axis=1, keepdims=True)
            S = X @ X.T
            tr = np.trace(S)
            if tr > 0:
                C += S / tr
        return C / max(1, len(idx))
    ia = np.flatnonzero(y == 0)
    ib = np.flatnonzero(y == 1)
    if ia.size < 2 or ib.size < 2:
        return None
    Ca, Cb = cov(ia), cov(ib)
    p = E.shape[1]
    Ca += reg * np.trace(Ca) / p * np.eye(p)
    Cb += reg * np.trace(Cb) / p * np.eye(p)
    try:
        from scipy.linalg import eigh
        w, V = eigh(Ca, Ca + Cb)
    except Exception:                                                       # noqa: BLE001
        return None
    order = np.argsort(w)
    sel = np.concatenate([order[:n_comp], order[-n_comp:]])
    return V[:, sel]


def csp_features(E, W):
    """log-variance of each projected component, the standard CSP feature."""
    out = np.empty((E.shape[0], W.shape[1]))
    for t in range(E.shape[0]):
        Z = W.T @ (E[t] - E[t].mean(axis=1, keepdims=True))
        v = np.var(Z, axis=1)
        s = v.sum()
        out[t] = np.log(np.clip(v / s if s > 0 else v, 1e-12, None))
    return out


def cv_auc(E, y, rng, folds=FOLDS):
    """5-fold CV AUC with CSP REFIT INSIDE EACH TRAINING FOLD (see the docstring)."""
    n = E.shape[0]
    idx = rng.permutation(n)
    pred = np.full(n, np.nan)
    for f in range(folds):
        te = idx[f::folds]
        tr = np.setdiff1d(idx, te)
        if tr.size < 8 or te.size < 1:
            continue
        if len(np.unique(y[tr])) < 2:
            continue
        W = csp_filters(E[tr], y[tr])
        if W is None:
            continue
        Xtr, Xte = csp_features(E[tr], W), csp_features(E[te], W)
        mu, sd = Xtr.mean(axis=0), Xtr.std(axis=0)
        sd[sd <= 0] = 1.0
        try:
            beta = logit_fit((Xtr - mu) / sd, y[tr])
            pred[te] = predict_proba((Xte - mu) / sd, beta)
        except Exception:                                                   # noqa: BLE001
            continue
    ok = np.isfinite(pred)
    return auc(y[ok], pred[ok]) if ok.sum() > 4 and len(np.unique(y[ok])) == 2 else float("nan")


def subject_epochs(sub):
    """All imagery trials for one subject, 64 channels, band-passed, epoched 0.5-3.5 s post-cue."""
    E, y = [], []
    n_ch = 0
    for run in IMAGERY_RUNS:
        evs = eegmmidb.events(sub, run)
        dur = eegmmidb.record_duration_s(sub, run)
        data, ch, sf, _ = eegmmidb.read_window(sub, run, 0.0, dur)
        X = bandpass(np.asarray(data, float), float(sf), *BAND)
        n_ch = X.shape[0]
        a, b = int(round(EPOCH[0] * sf)), int(round(EPOCH[1] * sf))
        for onset, label, _d in evs:
            if label not in ("T1", "T2"):
                continue
            s0 = int(round(onset * sf)) + a
            s1 = s0 + (b - a)
            if s0 < 0 or s1 > X.shape[1]:
                continue
            seg = X[:, s0:s1]
            if not np.isfinite(seg).all():
                continue
            E.append(seg)
            y.append(1.0 if label == "T2" else 0.0)
    if not E:
        return None, None, 0
    return np.stack(E), np.asarray(y, float), n_ch


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--of", type=int, default=1)
    a = ap.parse_args(argv)

    subs = [s for i, s in enumerate(eegmmidb.subjects()) if i % a.of == a.shard]
    out_path = os.path.abspath(a.out)
    done = set()
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        with open(out_path, newline="") as fh:
            done = {r["subject"] for r in csv.DictReader(fh)}
    todo = [s for s in subs if s not in done]
    if a.limit:
        todo = todo[:a.limit]
    print(f"shard {a.shard}/{a.of}: {len(subs)} subjects, {len(done)} done, {len(todo)} to do",
          flush=True)

    new = not os.path.exists(out_path) or os.path.getsize(out_path) == 0
    with open(out_path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        if new:
            w.writeheader()
        for i, sub in enumerate(todo, 1):
            row = {"subject": sub, "status": "ok", "error": "", "n_perm": N_PERM}
            try:
                E, y, n_ch = subject_epochs(sub)
                if E is None or E.shape[0] < 20 or len(np.unique(y)) < 2:
                    raise ValueError(f"only {0 if E is None else E.shape[0]} usable trials")
                rng = np.random.default_rng(SEED + int(sub[1:]))
                real = cv_auc(E, y, rng)
                null = np.array([cv_auc(E, rng.permutation(y), rng) for _ in range(N_PERM)], float)
                nf = null[np.isfinite(null)]
                p = float((np.sum(nf >= real) + 1) / (nf.size + 1)) if nf.size else float("nan")
                row.update({"csp_auc": f"{real:.6f}", "perm_p": f"{p:.6f}",
                            "perm_null_mean": f"{float(np.mean(nf)):.6f}" if nf.size else "",
                            "n_trials": int(E.shape[0]), "n_left": int((y == 0).sum()),
                            "n_right": int((y == 1).sum()), "n_channels": int(n_ch)})
            except Exception as e:                                          # noqa: BLE001
                row["status"], row["error"] = "error", f"{type(e).__name__}: {e}"
            w.writerow(row)
            fh.flush()
            print(f"[{i}/{len(todo)}] {sub} {row['status']} auc={row.get('csp_auc','')[:6]} "
                  f"p={row.get('perm_p','')[:6]} nullmean={row.get('perm_null_mean','')[:6]}",
                  flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
