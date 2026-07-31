"""Network measures on eegmmidb RESTING runs -- the external replication cohort Challenge B has never had.

WHY. E86 is Challenge B's only positive: `ge_norm` predicts BCI accuracy between subjects at D1 rho
+0.3069 [+0.0495, +0.5343] in 62 Stieger subjects. E97 showed it is trait-like, E101 could not separate the
trait model from noise at n = 61, and E106 showed it is NOT individual alpha frequency restated
(rho(ge_norm, iaf) = +0.0781; partials +0.2837 and +0.2423). **Every one of those is the same 62 subjects.**

The binding limitation that survived all of them is multiplicity: **BH q = 0.0920** across the E86 family.
A correction cannot be argued away and a bigger analysis of the same cohort does not touch it.
**A single pre-registered hypothesis tested once in an independent cohort does.**

eegmmidb is that cohort and it is already partly on disk: `eegmmidb_bci.csv` carries a cross-validated
`imagery_auc` per subject with its own permutation p for **105 subjects** -- an outcome computed long
before this script existed and with no network measure anywhere near it. What is missing is the predictor,
because no graph measures have ever been computed on the resting runs. This adds them.

WHAT IS COPIED EXACTLY, AND WHY THAT MATTERS MORE THAN ANYTHING ELSE HERE. `graph_features`,
`periodic_features`, `_efficiency`, `_clustering`, `_modularity` and `_null_graphs` are IMPORTED from
`extract_stieger_graph62.py`, not reimplemented. A replication that recomputes its predictor with new code
is not a replication of the same quantity (rule 20), and the temptation to "clean up" an estimator while
porting it is exactly how a failed replication becomes uninterpretable.

WHAT NECESSARILY DIFFERS, stated so no one has to infer it from the code:
  * 64 channels here against Stieger's 62, and a different montage. `ge_norm` is null-normalised, which is
    what makes it comparable across graph sizes at all -- and that normalisation is the reason E86's
    primary was chosen over raw `ge`.
  * 160 Hz sampling against 1000 Hz. The alpha band and the wPLI window are specified in seconds and hertz,
    so this changes resolution and not definition.
  * **Resting runs (R01 eyes-open, R02 eyes-closed), not pre-cue baselines.** Stieger's predictor came from
    the pre-cue period of task trials. This is a genuine difference in what "resting" means and it is a
    limitation of the replication, not a detail: if `ge_norm` replicates it replicates on a DIFFERENT
    resting state, and if it fails, that is one of the available explanations.
  * The two runs are emitted as separate rows so an experiment can average them, use one, or test whether
    the eyes-open/eyes-closed distinction matters -- decisions that belong in a registered analysis and not
    in an extractor.

SCOPE. This script extracts. It reads no accuracy, computes no contrast and makes no claim.

    python bsde/scripts/extract_eegmmidb_graph.py --limit 4        # smoke
    python bsde/scripts/extract_eegmmidb_graph.py --shard k --of 4 # full, resumable
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

from bsde.features.connectivity import wpli_matrix                          # noqa: E402
from bsde.ingestion import eegmmidb                                        # noqa: E402
# the ONLY correct source for these -- see the docstring (rule 20)
from extract_stieger_graph62 import graph_features                         # noqa: E402

OUT = os.path.join(HERE, "..", "results", "eegmmidb_graph.csv")
REST_RUNS = ("R01", "R02")
WINDOW_S = 55.0
ALPHA_LO, ALPHA_HI = 8.0, 13.0
WPLI_WINDOW_S, WPLI_OVERLAP = 2.0, 0.5
SEED = 20260731

GRAPH_KEYS = ["ge", "cl", "deg", "ge_norm", "cl_norm", "smallworld", "modularity", "strength_cv"]
FIELDS = (["recording_id", "subject", "run", "status", "error", "n_channels", "sfreq", "n_samples"]
          + GRAPH_KEYS + ["iaf", "alpha_prom"])


def periodic_features_at(X, sfreq):
    """IAF and its prominence above the aperiodic fit, median over channels.

    `extract_stieger_graph62.periodic_features` hardcodes Stieger's 1000 Hz through a module constant, so
    it cannot be imported for a 160 Hz deposit. The BODY is transcribed unchanged apart from taking sfreq
    as an argument -- and that difference is written down here rather than hidden, because a silently
    diverging copy is what rule 20 exists to prevent.
    """
    from bsde.features.aperiodic import fit_aperiodic, welch_psd
    iafs, proms = [], []
    for c in range(X.shape[0]):
        try:
            f, p = welch_psd(X[c], sfreq, window_s=1.0, overlap=0.5)
            fit = fit_aperiodic(f, p, 1.0, 40.0, "loglog_robust")
            bg = 10.0 ** (fit["offset"] - fit["exponent"] * np.log10(np.clip(f, 1e-9, None)))
            band = (f >= 7.0) & (f <= 13.0)
            if band.sum() < 2:
                continue
            resid = (np.log10(np.clip(p[band], 1e-30, None))
                     - np.log10(np.clip(bg[band], 1e-30, None)))
            k = int(np.argmax(resid))
            iafs.append(float(f[band][k]))
            proms.append(float(resid[k]))
        except Exception:                                                   # noqa: BLE001
            continue
    return {"iaf": float(np.nanmedian(iafs)) if iafs else float("nan"),
            "alpha_prom": float(np.nanmedian(proms)) if proms else float("nan")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--of", type=int, default=1)
    a = ap.parse_args(argv)

    subs = eegmmidb.subjects()
    work = [(s, r) for s in subs for r in REST_RUNS]
    work = [w for i, w in enumerate(work) if i % a.of == a.shard]
    out_path = os.path.abspath(a.out)
    done = set()
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        with open(out_path, newline="") as fh:
            done = {r["recording_id"] for r in csv.DictReader(fh)}
    todo = [(s, r) for s, r in work if f"{s}{r}" not in done]
    if a.limit:
        todo = todo[:a.limit]
    print(f"shard {a.shard}/{a.of}: {len(subs)} subjects, {len(work)} (subject, run) pairs, "
          f"{len(done)} done, {len(todo)} to do -> {out_path}", flush=True)

    rng = np.random.default_rng(SEED + a.shard)
    new = not os.path.exists(out_path) or os.path.getsize(out_path) == 0
    n_ok = n_err = 0
    with open(out_path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        if new:
            w.writeheader()
        for i, (sub, run) in enumerate(todo, 1):
            row = {"recording_id": f"{sub}{run}", "subject": sub, "run": run,
                   "status": "ok", "error": ""}
            try:
                data, ch, sf, _ = eegmmidb.read_window(sub, run, 0.0, WINDOW_S)
                X = np.asarray(data, float)
                if not np.isfinite(X).all():
                    raise ValueError("non-finite samples in the window")
                row["n_channels"], row["sfreq"], row["n_samples"] = X.shape[0], float(sf), X.shape[1]
                W = wpli_matrix(X, float(sf), ALPHA_LO, ALPHA_HI,
                                window_s=WPLI_WINDOW_S, overlap=WPLI_OVERLAP, debias=True)
                row.update(graph_features(W, rng))
                row.update(periodic_features_at(X, float(sf)))
                n_ok += 1
            except Exception as e:                                          # noqa: BLE001
                row["status"], row["error"] = "error", f"{type(e).__name__}: {e}"
                n_err += 1
                if n_err <= 5:
                    print(f"   FAIL {sub}{run}: {row['error']}", flush=True)
            w.writerow(row)
            fh.flush()
            if i % 20 == 0:
                print(f"   [{i}/{len(todo)}] ok={n_ok} err={n_err}", flush=True)
    print(f"done: {n_ok} ok, {n_err} failed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
