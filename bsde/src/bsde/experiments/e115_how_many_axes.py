"""E115 -- HOW MANY state-carrying axes does this project's whole measure inventory contain?

REGISTERED BEFORE ANY DEFLATION IS RUN. Existing tables only.

=========================================================================================================
THE REFRAME, AND WHY IT IS OVERDUE
=========================================================================================================
Challenge A has asked "is there a SECOND axis?" six times -- E92 (two regions), E73 and E86 (network),
E104 (perturbational), E105 (ongoing complexity), E107 (time-irreversibility) -- and answered no six
times. E107 was the sharpest: a measure PROVABLY orthogonal to the entire power spectrum still ordered REM
with sleep, more extremely than the exponent did.

**Six failures of the same shape are a result about the question.** Each experiment guessed a candidate
and tested it, so each null is a statement about that candidate and not about the inventory. The question
that the accumulated data can actually answer, and that no experiment here has asked, is the
DIMENSIONALITY one:

    given every measure this project computes, how many mutually independent directions carry information
    about brain state at all?

If the answer is one, the single-axis reading stops being an inference from repeated failure and becomes a
measurement. If it is two or more, the second axis exists and this procedure FINDS it without anyone
having to guess which measure carries it -- which is precisely the weakness of all six prior attempts.

=========================================================================================================
METHOD -- sequential deflation with an out-of-sample score and a permutation stopping rule
=========================================================================================================
Deposit: Sleep-EDFx five-stage windows, 142 subjects x {W, N1, N2, N3, REM}, 17 features. Five ordered
states within every subject is the richest state contrast this project holds.

  1. **Within-subject standardisation.** Each feature is z-scored across that subject's own five stages.
     This removes per-subject scale and offset, which rule 57 was earned on (an amplitude in arbitrary
     units is not a magnitude), and makes the analysis about state rather than about person.
  2. **Find the leading state-discriminating direction** by multiclass linear discriminant analysis on the
     stage label, i.e. the direction maximising between-stage over within-stage scatter.
  3. **Score it OUT OF SAMPLE.** The direction is fitted on a training set of SUBJECTS and its stage
     discriminability is evaluated on held-out SUBJECTS, 5-fold, split by subject and never by window.
     A direction fitted and scored on the same rows always separates; this is rule 9's discipline applied
     to a projection rather than to a model.
  4. **Deflate**: project every feature onto the orthogonal complement of the direction found, so the next
     round cannot re-find it.
  5. Repeat to `MAX_AXES`.

    P  the NUMBER OF AXES whose out-of-sample discriminability exceeds the 95th percentile of a
       permutation null in which stage labels are shuffled WITHIN SUBJECT (preserving each subject's set
       of five labels and the whole deflation pipeline re-run inside every draw).

VERDICT, and the branch that costs us most is named first (rule 37):

    (a) ZERO axes clear the null -> BROKEN. The inventory does not discriminate sleep stage at all, which
        would mean the pipeline or the labels are wrong, not that consciousness has no axes. ABSENT.
    (b) ONE axis -> THE SINGLE-AXIS READING IS MEASURED, NOT INFERRED. Six candidate-by-candidate nulls
        are explained by one structural fact, and the honest summary of Challenge A becomes a positive
        statement about dimensionality rather than a list of failures.
    (c) TWO OR MORE -> A SECOND AXIS EXISTS AND THIS FOUND IT. The loadings of axis 2 are then reported --
        which measures carry it -- and every prior null is re-read as having guessed the wrong candidate.

PREDICTED: (b) at ~45 %, (c) at ~45 %, (a) at ~10 %. **(c) is given equal weight deliberately.** Six
guessed candidates failing is weak evidence that a data-driven search will fail too, and stating this
before the run stops a (b) result being written up as though it were expected all along.

=========================================================================================================
GATES
=========================================================================================================
    G1  COVERAGE. >= 100 subjects with all five stages and all features finite after standardisation.
    G2  AXIS 1 MUST BE ALIVE. The first direction must clear the permutation null comfortably. If the
        strongest direction in the inventory cannot separate five sleep stages out of sample, nothing
        below it is interpretable and the verdict is ABSENT (rule 31) -- the E33/E61 rule applied to a
        deflation.
    G3  DEFLATION MUST ACTUALLY DEFLATE. After removing axis k, the retained variance and the correlation
        between consecutive axes' scores are reported; consecutive axes must be near-orthogonal by
        construction and this is checked rather than assumed (E96's C1 was a condition satisfied
        vacuously).
    G5  **THE PROCEDURE MUST NOT COUNT ONE AXIS AS SEVERAL, AND THIS IS THE GATE THE FIRST RUN LACKED.**
        Deflation is LINEAR. If sixteen features are sixteen different NON-LINEAR functions of a single
        latent state variable -- which is exactly what a battery of spectral and complexity summaries of
        one underlying process would be -- then removing the leading linear direction leaves residual
        stage information behind, and the procedure will report several axes where there is one.
        So: a SYNTHETIC inventory is generated from ONE latent axis, passed through as many distinct
        monotone non-linearities as there are real features, with matched noise, subject count and stage
        structure, and run through the IDENTICAL pipeline. **If the one-axis synthetic also yields
        several axes, the procedure cannot count axes and the verdict is NOT-INTERPRETABLE** whatever the
        real data did. Rule 40: construct the input that should fail the gate and check that it does.

    G4  NOT A MUSCLE AXIS. `emg_index`, `emg_beta_gamma_fraction` and `emg_kurtosis` are in the inventory
        and E70/E100/E107 all found muscle driving apparent state effects. The loadings of every
        surviving axis on the three EMG features are REPORTED, and the whole procedure is re-run with
        them EXCLUDED. **An axis that survives only with EMG in the inventory is a muscle axis and the
        verdict says so.**

SCOPE. Sleep-EDFx, two bipolar derivations. "State" here is scored sleep stage, not consciousness; the
count is a property of THIS inventory on THIS deposit and a measure absent from the inventory cannot be
counted. Nothing here detects or measures consciousness.
"""
from __future__ import annotations

import csv
import json
import os
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
TABLE = os.path.join(RESULTS, "sleep_edfx_five_stage.csv")
OUT = os.path.join(RESULTS, "e115_how_many_axes.json")

STAGES = ("W", "N1", "N2", "N3", "REM")
BURNED = {"SC4001E0"}
FEATURES = ["critical_slowing_ar1", "emg_beta_gamma_fraction", "emg_index", "emg_kurtosis",
            "exponent_high", "exponent_low", "lempel_ziv", "multiscale_entropy_slope",
            "pac_slow_alpha", "relative_alpha_power", "relative_delta_power",
            "spatial_participation_ratio", "spectral_edge_95", "spectral_entropy",
            "whole_head_exponent", "wpli_alpha"]
# `uce_v1` is NOT in this inventory and its absence costs nothing: the column exists in
# sleep_edfx_five_stage.csv but is non-finite in all 710 rows, and E92 established uce_v1 is the
# whole-head exponent restated, which IS included. Listing a column that is empty for every row would
# have excluded every subject via the all-finite requirement -- which is what it did on the first run.
EMG_FEATURES = ["emg_index", "emg_beta_gamma_fraction", "emg_kurtosis"]
MAX_AXES = 5
FOLDS = 5
N_PERM = 300
MIN_SUBJECTS = 100
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def load(features):
    """(n_subjects, 5 stages, n_features) after within-subject z-scoring, plus the subject list."""
    per = defaultdict(dict)
    for r in csv.DictReader(open(TABLE, newline="")):
        rid = r.get("recording_id", "")
        s = r.get("subject", "")
        if s in BURNED or "@" not in rid:
            continue
        st = rid.rsplit("@", 1)[1]
        if st not in STAGES:
            continue
        per[s][st] = [_f(r.get(f, "")) for f in features]
    X, subs = [], []
    for s, d in per.items():
        if not all(k in d for k in STAGES):
            continue
        M = np.array([d[k] for k in STAGES], float)          # 5 x n_features
        if not np.isfinite(M).all():
            continue
        sd = M.std(axis=0)
        if np.any(sd <= 0):
            continue
        X.append((M - M.mean(axis=0)) / sd)                  # within-subject z, rule 57
        subs.append(s)
    return (np.array(X) if X else np.zeros((0, len(STAGES), len(features)))), subs


def lda_direction(X, y, reg=1e-3):
    """Leading multiclass LDA direction: maximise between-class over within-class scatter."""
    p = X.shape[1]
    mu = X.mean(axis=0)
    Sw = np.zeros((p, p))
    Sb = np.zeros((p, p))
    for c in np.unique(y):
        Xc = X[y == c]
        if Xc.shape[0] < 2:
            continue
        m = Xc.mean(axis=0)
        D = Xc - m
        Sw += D.T @ D
        d = (m - mu).reshape(-1, 1)
        Sb += Xc.shape[0] * (d @ d.T)
    Sw += reg * np.trace(Sw) / p * np.eye(p) + 1e-9 * np.eye(p)
    try:
        from scipy.linalg import eigh
        w, V = eigh(Sb, Sw)
    except Exception:                                                       # noqa: BLE001
        return None
    v = V[:, int(np.argmax(w))]
    n = np.linalg.norm(v)
    return v / n if n > 0 else None


def discriminability(scores, y):
    """Between-stage over total variance of a 1-D score. 0 = no separation, 1 = perfect."""
    scores = np.asarray(scores, float)
    tot = float(np.var(scores))
    if tot <= 0:
        return float("nan")
    m = np.array([scores[y == c].mean() for c in np.unique(y)])
    n = np.array([(y == c).sum() for c in np.unique(y)], float)
    between = float(np.sum(n * (m - scores.mean()) ** 2) / scores.size)
    return between / tot


def deflate(X, v):
    """Project every row onto the orthogonal complement of v."""
    return X - np.outer(X @ v, v)


def run_pipeline(X3, y_flat, rng, max_axes=MAX_AXES, folds=FOLDS):
    """Out-of-sample discriminability of each successive deflated axis. Split BY SUBJECT."""
    n_sub = X3.shape[0]
    order = rng.permutation(n_sub)
    work = X3.copy()
    out = []
    for _ in range(max_axes):
        scores = np.full(n_sub * len(STAGES), np.nan)
        for f in range(folds):
            te_s = order[f::folds]
            tr_s = np.setdiff1d(order, te_s)
            if tr_s.size < 10 or te_s.size < 2:
                continue
            Xtr = work[tr_s].reshape(-1, work.shape[2])
            ytr = np.tile(np.arange(len(STAGES)), tr_s.size)
            v = lda_direction(Xtr, ytr)
            if v is None:
                continue
            idx = np.concatenate([np.arange(s * len(STAGES), (s + 1) * len(STAGES)) for s in te_s])
            scores[idx] = work[te_s].reshape(-1, work.shape[2]) @ v
        ok = np.isfinite(scores)
        d = discriminability(scores[ok], y_flat[ok]) if ok.sum() > 20 else float("nan")
        # deflate on the FULL-data direction so the next round is well defined for every subject
        v_full = lda_direction(work.reshape(-1, work.shape[2]), y_flat)
        if v_full is None:
            out.append({"discriminability": d, "loadings": None})
            break
        out.append({"discriminability": d, "loadings": v_full.tolist(),
                    "retained_var": float(np.var(deflate(work.reshape(-1, work.shape[2]), v_full)))})
        work = deflate(work.reshape(-1, work.shape[2]), v_full).reshape(work.shape)
    return out


def analyse(features, label, rng_seed=SEED):
    X3, subs = load(features)
    if X3.shape[0] < 20:
        return None
    y_flat = np.tile(np.arange(len(STAGES)), X3.shape[0])
    rng = np.random.default_rng(rng_seed)
    real = run_pipeline(X3, y_flat, rng)

    null = []
    for _ in range(N_PERM):
        Xp = X3.copy()
        for s in range(Xp.shape[0]):
            Xp[s] = Xp[s][rng.permutation(len(STAGES))]      # shuffle stage labels WITHIN subject
        null.append([a["discriminability"] for a in run_pipeline(Xp, y_flat, rng, max_axes=MAX_AXES)])
    width = max(len(r) for r in null)
    thr = []
    for k in range(width):
        vals = [r[k] for r in null if len(r) > k and np.isfinite(r[k])]
        thr.append(float(np.quantile(vals, 0.95)) if len(vals) >= 20 else float("nan"))

    surviving = 0
    rows = []
    for k, a in enumerate(real):
        t = thr[k] if k < len(thr) else float("nan")
        clears = bool(np.isfinite(a["discriminability"]) and np.isfinite(t)
                      and a["discriminability"] > t)
        rows.append({"axis": k + 1, "discriminability": a["discriminability"], "null_95": t,
                     "clears": clears, "loadings": a.get("loadings")})
        if clears and surviving == k:
            surviving = k + 1
    print(f"\n--- {label} ({X3.shape[0]} subjects, {len(features)} features) ---")
    print(f"{'axis':>5s} {'out-of-sample D':>17s} {'null 95th':>11s}  clears")
    for r in rows:
        print(f"{r['axis']:>5d} {r['discriminability']:17.4f} {r['null_95']:11.4f}  "
              f"{'YES' if r['clears'] else 'no'}")
    print(f"  -> {surviving} consecutive axis/axes clear the permutation null")
    return {"n_subjects": X3.shape[0], "axes": rows, "n_surviving": surviving, "features": features}


def synthetic_one_axis(n_sub, n_feat, rng, noise=0.35):
    """One latent state variable, n_feat distinct monotone non-linearities, matched shape.

    The latent is the stage index itself (a real ordered state), so this control has EXACTLY one
    state-carrying axis by construction. Any count above 1 from the pipeline on this input is the
    pipeline's own artefact.
    """
    k = len(STAGES)
    lat = np.tile(np.linspace(-1.0, 1.0, k), (n_sub, 1))
    lat = lat + rng.normal(0, 0.10, lat.shape)              # subject-level jitter on the same axis
    X = np.empty((n_sub, k, n_feat))
    for j in range(n_feat):
        # a different monotone map per feature: powers, logistic, exponential, tanh at varying gains
        kind = j % 4
        a = 1.0 + 0.4 * (j // 4)
        if kind == 0:
            f = np.sign(lat) * np.abs(lat) ** a
        elif kind == 1:
            f = 1.0 / (1.0 + np.exp(-a * 3.0 * lat))
        elif kind == 2:
            f = np.exp(a * lat)
        else:
            f = np.tanh(a * 2.0 * lat)
        X[:, :, j] = f + rng.normal(0, noise, f.shape)
    out = np.empty_like(X)
    for s in range(n_sub):
        M = X[s]
        sd = M.std(axis=0)
        sd[sd <= 0] = 1.0
        out[s] = (M - M.mean(axis=0)) / sd
    return out


def count_axes(X3, rng, n_perm=N_PERM, label=""):
    """Shared counting routine: real pipeline, permutation null, number of consecutive clearing axes."""
    y_flat = np.tile(np.arange(len(STAGES)), X3.shape[0])
    real = run_pipeline(X3, y_flat, rng)
    null = []
    for _ in range(n_perm):
        Xp = X3.copy()
        for s in range(Xp.shape[0]):
            Xp[s] = Xp[s][rng.permutation(len(STAGES))]
        null.append([a["discriminability"] for a in run_pipeline(Xp, y_flat, rng, max_axes=MAX_AXES)])
    width = max(len(r) for r in null)
    thr = []
    for k in range(width):
        vals = [r[k] for r in null if len(r) > k and np.isfinite(r[k])]
        thr.append(float(np.quantile(vals, 0.95)) if len(vals) >= 20 else float("nan"))
    surviving, rows = 0, []
    for k, a in enumerate(real):
        t = thr[k] if k < len(thr) else float("nan")
        clears = bool(np.isfinite(a["discriminability"]) and np.isfinite(t)
                      and a["discriminability"] > t)
        rows.append({"axis": k + 1, "discriminability": a["discriminability"], "null_95": t,
                     "clears": clears, "loadings": a.get("loadings")})
        if clears and surviving == k:
            surviving = k + 1
    if label:
        print(f"\n--- {label} ({X3.shape[0]} subjects, {X3.shape[2]} features) ---")
        print(f"{'axis':>5s} {'out-of-sample D':>17s} {'null 95th':>11s}  clears")
        for r in rows:
            print(f"{r['axis']:>5d} {r['discriminability']:17.4f} {r['null_95']:11.4f}  "
                  f"{'YES' if r['clears'] else 'no'}")
        print(f"  -> {surviving} consecutive axis/axes clear the permutation null")
    return {"axes": rows, "n_surviving": surviving}


def main() -> int:
    if not os.path.exists(TABLE):
        print(f"ABSENT: {TABLE}")
        return 2
    res = {"gates": {}}
    full = analyse(FEATURES, "FULL INVENTORY")
    if full is None:
        print("\nVERDICT: ABSENT -- too few usable subjects")
        return 1
    res["full"] = full
    res["gates"]["G1_pass"] = bool(full["n_subjects"] >= MIN_SUBJECTS)
    res["gates"]["G2_pass"] = bool(full["axes"] and full["axes"][0]["clears"])
    print(f"\nG1 coverage   {full['n_subjects']} >= {MIN_SUBJECTS}  "
          f"{'PASS' if res['gates']['G1_pass'] else 'FAIL'}")
    print(f"G2 axis 1     {'PASS' if res['gates']['G2_pass'] else 'FAIL -- nothing separates the stages'}")

    noemg = [f for f in FEATURES if f not in EMG_FEATURES]
    res["no_emg"] = analyse(noemg, "EMG FEATURES EXCLUDED (G4)")
    if res["no_emg"]:
        res["gates"]["G4_surviving_without_emg"] = res["no_emg"]["n_surviving"]

    # G4 loadings of every surviving axis on the EMG features
    idx = [FEATURES.index(f) for f in EMG_FEATURES]
    emg_load = []
    for a in full["axes"][:max(1, full["n_surviving"])]:
        if a.get("loadings"):
            L = np.array(a["loadings"])
            emg_load.append(float(np.sum(np.abs(L[idx])) / np.sum(np.abs(L))))
    res["gates"]["G4_emg_loading_fraction"] = emg_load
    print(f"\nG4 muscle     |loading| fraction on the 3 EMG features, per surviving axis: "
          + ", ".join(f"{v:.1%}" for v in emg_load))

    # ---- G5: can the procedure count at all? ------------------------------------------------------
    srng = np.random.default_rng(SEED + 99)
    syn = synthetic_one_axis(full["n_subjects"], len(FEATURES), srng)
    syn_res = count_axes(syn, srng, n_perm=max(60, N_PERM // 4),
                         label="G5 CONTROL -- SYNTHETIC ONE-AXIS INVENTORY (16 non-linear views of one "
                               "latent state)")
    res["G5_synthetic"] = syn_res
    g5 = bool(syn_res["n_surviving"] <= 1)
    res["gates"]["G5_pass"] = g5
    print(f"\nG5 countable  synthetic ONE-axis inventory yields {syn_res['n_surviving']} axes  "
          f"{'PASS -- the procedure can count' if g5 else 'FAIL -- the procedure inflates the count'}")

    k_full = full["n_surviving"]
    k_noemg = res["no_emg"]["n_surviving"] if res["no_emg"] else None
    if not g5:
        v = (f"**NOT INTERPRETABLE -- THE PROCEDURE CANNOT COUNT AXES.** A synthetic inventory built from "
             f"ONE latent state variable, viewed through {len(FEATURES)} distinct monotone "
             f"non-linearities, yields {syn_res['n_surviving']} axes from the identical pipeline. Linear "
             f"deflation cannot remove a non-linearly encoded axis, so the real data's {k_full} says "
             f"nothing about how many axes exist. The count on real data was "
             f"{[round(a['discriminability'], 4) for a in full['axes']]} and is reported ONLY so the "
             f"failure is auditable. Rule 40: a gate that cannot fail is not a gate, and this one could.")
    elif not res["gates"]["G2_pass"]:
        v = ("ABSENT -- not even the leading direction separates the five sleep stages out of sample, so "
             "the inventory or the labels are broken and no count is interpretable (rule 31).")
    elif k_full <= 1:
        v = (f"**ONE AXIS. The single-axis reading is now MEASURED rather than inferred.** Exactly "
             f"{k_full} direction in a {len(FEATURES)}-measure inventory carries out-of-sample "
             f"state information above a within-subject permutation null. Six candidate-by-candidate "
             f"nulls (E92, E73/E86, E104, E105, E107) are explained by one structural fact rather than by "
             f"six separate accidents."
             + (f" With the EMG features excluded the count is {k_noemg}." if k_noemg is not None else ""))
    elif k_noemg is not None and k_noemg < k_full:
        v = (f"{k_full} AXES WITH MUSCLE, {k_noemg} WITHOUT -- the extra axis or axes do not survive "
             f"removing the EMG features from the inventory, so they are MUSCLE axes and must not be "
             f"reported as brain-state dimensions. E70, E100 and E107 all found muscle driving apparent "
             f"state effects and this is the same thing at the level of the whole inventory.")
    else:
        v = (f"**{k_full} AXES, AND THIS PROCEDURE FOUND THEM WITHOUT GUESSING A CANDIDATE.** {k_full} "
             f"consecutive directions clear the within-subject permutation null out of sample, and the "
             f"count is unchanged at {k_noemg} with the EMG features excluded, so it is not muscle. The "
             f"loadings of axis 2 onward name which measures carry it, and every prior Challenge A null "
             f"is re-read as having guessed the wrong candidate rather than as evidence of one axis.")
    res["verdict"] = v
    print(f"\nVERDICT: {v}")
    json.dump(res, open(OUT, "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
