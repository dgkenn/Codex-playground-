"""Build Challenge B's LABEL: per-subject motor-imagery decoding accuracy, from the task runs only.

WHAT THE LABEL IS. For each subject, how well can left-fist versus right-fist **imagined** movement be
decoded from their own EEG? That is command-following that produces no movement — the subject is
instructed, complies covertly, and the only evidence is the signal. It is the closest reachable analogue of
covert command-following in a disorder of consciousness, and unlike that population it can be scored.

HOW IT IS COMPUTED, AND WHY EACH CHOICE IS THE BORING ONE. The point of this file is to produce an honest
label, not a good decoder; a clever decoder would make the label depend on modelling choices nobody
registered.

  * **Features: log band power at C3, C4 and Cz in mu (8-13 Hz) and beta (13-30 Hz).** The textbook
    sensorimotor-rhythm feature set. No CSP, no spatial filter learned from the data — a learned spatial
    filter would make per-subject accuracy depend on how much data that subject supplied, which varies.
  * **Epoch: 0.5-3.5 s after cue onset**, the standard motor-imagery window, avoiding the cue-evoked
    transient at onset and the return-to-rest at the end.
  * **Classifier: logistic regression, 5-fold cross-validation WITHIN the subject**, scored by AUC. Every
    fold's standardisation is fitted on its training rows only. Accuracy is out-of-fold by construction:
    an in-sample score would be near-perfect for every subject and would have no variance to predict.
  * **Rest trials (T0) are discarded.** The contrast is left versus right imagery, not task versus rest.
    Task-versus-rest is decodable from generic engagement and would score high in subjects who cannot
    actually control anything.

WHAT THIS FILE MUST NOT TOUCH. The baseline runs R01 and R02. Those are the SPONTANEOUS side of Challenge
B's question and are streamed separately by `stream_eegmmidb_rest.py`. If any feature here came from them
the association E28 tests would be circular.

A PERMUTATION SCORE IS COMPUTED FOR EVERY SUBJECT and written alongside, by relabelling trials within the
subject and re-running the identical pipeline. It is the per-subject answer to "is this subject's score
distinguishable from chance", and E28's machinery gate uses it rather than assuming 0.5 is the right null
for a small, unbalanced trial set.

    python bsde/scripts/build_eegmmidb_bci_label.py --out bsde/results/eegmmidb_bci.csv
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from bsde.ingestion.eegmmidb import (EXECUTED_LR_RUNS, IMAGERY_LR_RUNS,     # noqa: E402
                                     events, read_window, record_duration_s, subjects)
from bsde.verifier.stats import auc, logit_fit, predict_proba              # noqa: E402

BANDS = (("mu", 8.0, 13.0), ("beta", 13.0, 30.0))
CHANNELS = ("C3..", "C4..", "Cz..")
EPOCH = (0.5, 3.5)
FOLDS = 5
N_PERM = 200
MIN_TRIALS_PER_CLASS = 8


def _band_power(seg: np.ndarray, sfreq: float) -> np.ndarray:
    from numpy.fft import rfft, rfftfreq
    w = np.hanning(seg.shape[1])
    P = np.abs(rfft(seg * w, axis=1)) ** 2
    f = rfftfreq(seg.shape[1], 1.0 / sfreq)
    out = []
    for _, lo, hi in BANDS:
        m = (f >= lo) & (f < hi)
        out.append(np.log(P[:, m].sum(axis=1) + 1e-20))
    return np.concatenate(out)


def _cv_auc(X: np.ndarray, y: np.ndarray, rng, folds: int = FOLDS) -> float:
    """Out-of-fold AUC. Standardisation is fitted per training fold, never on the whole set."""
    n = len(y)
    if len(np.unique(y)) < 2:
        return float("nan")
    order = rng.permutation(n)
    fold = np.empty(n, int)
    fold[order] = np.arange(n) % folds
    pred = np.full(n, np.nan)
    for k in range(folds):
        te, tr = fold == k, fold != k
        if len(np.unique(y[tr])) < 2 or te.sum() == 0:
            continue
        mu, sd = X[tr].mean(axis=0), X[tr].std(axis=0)
        sd[sd == 0] = 1.0
        Xtr = np.column_stack([np.ones(tr.sum()), (X[tr] - mu) / sd])
        Xte = np.column_stack([np.ones(te.sum()), (X[te] - mu) / sd])
        try:
            pred[te] = predict_proba(Xte, logit_fit(Xtr, y[tr]))
        except Exception:                                                  # noqa: BLE001
            continue
    ok = np.isfinite(pred)
    return auc(y[ok], pred[ok]) if ok.sum() > 4 else float("nan")


def subject_label(sub: str, rng, runs=IMAGERY_LR_RUNS) -> dict:
    """One HTTP read PER RUN, not per trial, and the trials are sliced from the array in memory.

    The first version fetched a window per trial -- 45 EDF reads per subject over HTTPS -- and did not
    finish two subjects in two minutes. The run is 125 s of 64 channels at 160 Hz, about 2.5 MB, so reading
    it whole is cheaper than reading forty-five pieces of it and is also the only way the epoch boundaries
    are guaranteed to come from one consistent decode.
    """
    ch_idx, X, y = None, [], []
    for run in runs:
        try:
            ev = events(sub, run)
            full, names, sf, _ = read_window(sub, run, 0.0, record_duration_s(sub, run))
        except Exception as e:                                             # noqa: BLE001
            return {"subject": sub, "status": "error", "error": f"{run}: {type(e).__name__}: {e}"}
        full = np.asarray(full, float)
        if ch_idx is None:
            ch_idx = [names.index(c) for c in CHANNELS if c in names]
            if len(ch_idx) < len(CHANNELS):
                return {"subject": sub, "status": "error",
                        "error": f"montage lacks {set(CHANNELS) - set(names)}"}
        n_ep = int(round((EPOCH[1] - EPOCH[0]) * sf))
        for onset, label, _dur in ev:
            if label == "T0":
                continue
            i0 = int(round((onset + EPOCH[0]) * sf))
            seg = full[ch_idx, i0:i0 + n_ep]
            if seg.shape[1] < n_ep or not np.isfinite(seg).all():
                continue
            X.append(_band_power(seg, sf))
            y.append(1.0 if label == "T2" else 0.0)          # T1 = left fist, T2 = right fist
    if not X:
        return {"subject": sub, "status": "error", "error": "no trials"}
    X, y = np.vstack(X), np.asarray(y, float)
    if min((y == 0).sum(), (y == 1).sum()) < MIN_TRIALS_PER_CLASS:
        return {"subject": sub, "status": "error",
                "error": f"trials per class {int((y == 0).sum())}/{int((y == 1).sum())}"}
    real = _cv_auc(X, y, rng)
    null = np.array([_cv_auc(X, rng.permutation(y), rng) for _ in range(N_PERM)], float)
    null = null[np.isfinite(null)]
    p = float((1 + (null >= real).sum()) / (1 + null.size)) if null.size else float("nan")
    return {"subject": sub, "status": "ok", "error": "",
            "imagery_auc": f"{real}", "perm_p": f"{p}",
            "perm_null_mean": f"{float(null.mean()) if null.size else float('nan')}",
            "n_trials": f"{len(y)}", "n_left": f"{int((y == 0).sum())}",
            "n_right": f"{int((y == 1).sum())}", "n_perm": f"{null.size}"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=os.path.join(HERE, "..", "results", "eegmmidb_bci.csv"))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--task", choices=["imagery", "executed"], default="imagery",
                    help="imagery = the label (covert command-following); executed = E28's PLACEBO, real "
                         "movement, which is decodable from signal quality and motor-cortex accessibility "
                         "rather than from covert compliance")
    a = ap.parse_args(argv)
    runs = IMAGERY_LR_RUNS if a.task == "imagery" else EXECUTED_LR_RUNS
    out = os.path.abspath(a.out)
    fields = ["subject", "status", "error", "imagery_auc", "perm_p", "perm_null_mean",
              "n_trials", "n_left", "n_right", "n_perm"]
    done = set()
    if os.path.exists(out) and os.path.getsize(out) > 0:
        with open(out, newline="") as fh:
            rd = csv.DictReader(fh)
            if list(rd.fieldnames or []) != fields:
                print("existing file has a different column set; refusing to append.")
                return 1
            done = {r["subject"] for r in rd}
        print(f"   resuming: {len(done)} subjects present", flush=True)
    todo = [s for s in subjects() if s not in done][: a.limit]
    rng = np.random.default_rng(20260730)
    new = not os.path.exists(out) or os.path.getsize(out) == 0
    with open(out, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        if new:
            w.writeheader()
        for i, sub in enumerate(todo, 1):
            row = subject_label(sub, rng, runs)
            w.writerow({k: row.get(k, "") for k in fields})
            fh.flush()
            print(f"   [{i}/{len(todo)}] {sub} {row.get('status')} "
                  f"auc={row.get('imagery_auc', '')[:6]} p={row.get('perm_p', '')[:6]}", flush=True)
    print(f"   wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
