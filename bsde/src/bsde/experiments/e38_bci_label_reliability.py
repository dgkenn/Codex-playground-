#!/usr/bin/env python3
"""E38 — how much of E28's label is real? Split-half reliability of per-subject BCI decoding.

THIS EXPERIMENT CANNOT PRODUCE A POSITIVE FINDING ABOUT ANY EEG FEATURE, AND THAT IS THE POINT.

It reads no resting-state candidate, touches no column from `eegmmidb_rest.csv`, and has no candidate,
incumbent or primary in the usual sense. It characterises a **label**. The only things it can conclude are
about the label's measurement properties, and one of the available conclusions is that Challenge B's
healthy-BCI substitution is not viable — which is the outcome the loop most needs and the one no
candidate-scoring experiment can reach.

WHY IT EXISTS. E28's machinery gate failed: 17 of 104 subjects (16.3 %) beat their own permutation null at
p < 0.05, against a registered floor of 20 %. The diagnosis recorded there is that the floor asked for the
wrong quantity — the BCI-illiteracy literature's 70-85 % is a **prevalence** measured over hundreds of
trials, and `eegmmidb`'s imagery protocol gives **45 trials per subject, about 22 per class, across
R04/R08/R12, and that is the entire deposit**. A significance rate at n = 45 is a statement about detection
power, not about how many of these people can drive a BCI.

`DISCOVERY_LOOP.md` §2 permits a successor only by changing the instrument, and lowering the floor would be
moving it however well the diagnosis reads. **So the instrument changes from a significance rate to a
reliability coefficient**, which is the quantity that actually determines whether a noisy per-subject label
can serve as a regression target at all:

    r_half   Spearman correlation, ACROSS SUBJECTS, between two independent decoding estimates built from
             disjoint halves of the same subject's trials.
    r_sb     the same corrected to full length by Spearman-Brown, 2r/(1+r) — the reliability of the label
             E28 would actually have used.
    ceiling  sqrt(r_sb). Classical attenuation: no resting-state feature, however good, can correlate with
             this label above the square root of its reliability. **That number is a property of the label
             and it bounds every future experiment on this deposit**, which is why it is worth more than
             E28's verdict would have been.

WHAT MAKES THIS ANSWERABLE NOW AND NOT BEFORE. `build_eegmmidb_bci_label.py` computed one band-power vector
per trial and discarded all of them, keeping the subject-level AUC. `scripts/dump_eegmmidb_trials.py` now
caches the trials, **importing `_band_power`, `CHANNELS`, `BANDS` and `EPOCH` from the builder rather than
reimplementing them**, so the cached features are the numbers the label was built from by construction.
G1 checks that anyway, because "by construction" has been wrong in this project before.

THE WITHIN-HALF ESTIMATOR IS DECLARED HERE AND IS DELIBERATELY KNOB-FREE. Each half holds about 22 trials,
roughly 11 per class. The builder's 5-fold CV would put four or five samples in a fold and would need an
RNG for the fold assignment, adding both noise and a seed to a quantity that is supposed to be a
measurement. **Within a half, the estimator is leave-one-out**: deterministic, no fold-size choice, and the
least arbitrary option at this size. The split itself is random, so it is repeated `N_SPLITS` times and
averaged — the reported reliability is the mean over splits, not one draw of it.

REGISTERED BEFORE THE TRIAL CACHE IS READ. Evaluated in this order; the failing branch is written first.

  G1  RULE-20 GATE, and no reliability number is computed until it passes. Recompute each subject's
      full-trial AUC from the cache with the builder's own 5-fold estimator, averaged over `N_G1_DRAWS`
      independent fold assignments (see the correction below for why averaged), and compare against the
      `imagery_auc` already stored in `eegmmidb_bci.csv`. The requirement is a Spearman correlation of at
      least `MIN_AGREEMENT` across subjects **and** a median absolute difference below `MAX_MEDIAN_DIFF`.
      If either fails, the cache is not the same quantity the label was built from and nothing below it
      means anything: ABSENT, not negative (rule 31).

  P1  THE PRIMARY, and it is descriptive rather than pass/fail. `r_half`, `r_sb` and `ceiling` for the
      IMAGERY label, with a subject-level bootstrap CI. **Registered reading, fixed now so it cannot be
      chosen later:** if `r_sb`'s interval includes 0, the imagery label carries no reliable between-subject
      variance and **E28's design is not viable on this deposit** — no feature can predict it, and that is a
      fact about the label rather than a negative about any feature. If the interval excludes 0, the ceiling
      is reported and compared against what E28 would have needed.

  P2  THE COMPARISON ARM: the identical computation for EXECUTED movement. This is the discriminating test
      between two very different diagnoses. If executed is reliable and imagery is not, the deposit supports
      per-subject labels and it is *imagery* that is too weak here — Challenge B's substitution is dead but
      the machinery is sound. If neither is reliable, **45 trials is simply too few for any per-subject
      label**, and the same verdict would follow for any task in this deposit. The two readings license
      different next steps, which is why P2 is registered rather than added afterwards.

  P3  THE PLACEBO, and it gates the interpretation of P1 (rule 34). Each subject's labels are permuted once,
      then split and decoded exactly as in P1. The split-half correlation of a destroyed label must be
      indistinguishable from zero. If it is not, the estimator is manufacturing agreement — through shared
      subject-level feature scale, or through anything else — and P1's number is that artefact plus
      whatever is real. **Evaluated after P1 and capable only of invalidating it**, never of rescuing it,
      and reported as NOT INFORMATIVE if P1's own interval includes zero (rule 48, which E37 produced).

  P4  REPORTED CONTEXT, no verdict. Reliability as a function of trials per half, at every count the deposit
      allows, so the shape of the curve is visible rather than one point on it. This is what a future deposit
      choice should be read against: it says how many trials a per-subject label of this kind needs.

VERDICT RULE, written before the run.

    NOT INTERPRETABLE   G1 failed, or P3 shows the estimator manufacturing agreement.
    LABEL NOT VIABLE    r_sb's interval includes 0 for imagery. Challenge B's healthy-BCI substitution
                        cannot be run on this deposit, and E28 is not merely gate-failed but unrunnable as
                        designed. P2 then says whether that is about imagery or about 45 trials.
    LABEL VIABLE        r_sb excludes 0. Report the ceiling; a successor to E28 may be registered against
                        it, and must state the ceiling in its own header.

SCOPE. `eegmmidb`, healthy adults, 64 channels at 160 Hz, one decoder (log band power at C3/C4/Cz in mu and
beta, logistic regression) — the same decoder E28's label used, because the question is about THAT label
and not about the best achievable decoding. A different decoder would have a different reliability, and
nothing here bounds what a better one could reach. **No sentence from this file may be written as a claim
about disorders of consciousness**, which is E28's standing scope limit and survives its gate failure.

--------------------------------------------------------------------------------------------------------
CORRECTION BEFORE THE FULL RUN: G1's FLOOR WAS ABOVE WHAT THE ESTIMATOR CAN REACH, WHICH IS ERROR-CATALOGUE
RULE 40 COMMITTED BY THIS FILE — a gate that cannot pass, registered on the same day E37's inverse (a check
that cannot fire) was catalogued as rule 48.

A smoke run on the part-finished cache (35 subjects) put the cache-vs-stored Spearman at **0.836**, under
the 0.90 floor. Before touching anything, the obvious rival explanation was measured: **how well does the
estimator agree with ITSELF?** The builder's `_cv_auc` assigns folds from an RNG, so two runs on identical
data give different numbers. Three independent seeds on the same cached trials:

    seed1 vs seed2   Spearman 0.8489        seed1 vs stored   0.8436
    seed1 vs seed3   Spearman 0.8785        seed2 vs stored   0.8671
    seed2 vs seed3   Spearman 0.8447        seed3 vs stored   0.8873

**The cache reproduces the stored label exactly as well as the estimator reproduces itself** — the two
columns occupy the same range. There is no discrepancy attributable to the cache, and a single-draw
comparison could not have shown one, because a floor of 0.90 sits above the estimator's own single-draw
reproducibility of ~0.85. Note that the left-hand column involves no comparison to the stored label at all,
so this diagnosis was obtained without observing anything about the cache's fidelity.

**The floor does not move. The estimator's precision does.** G1 now averages `N_G1_DRAWS` independent fold
assignments before comparing, which is the standard fix for Monte-Carlo noise and changes no threshold,
cohort or horizon — the same reasoning rule 46 gives for raising a resample count, and the same shape as
E37's estimator correction, which was likewise made after a gate failed and before any primary was
computed. Averaging three draws already lifts the agreement to **0.9033**.

**A ceiling worth stating, because it makes G1 a demanding gate rather than a formality.** Averaging helps
only my side of the comparison; the stored value remains a single draw. With single-draw reliability around
0.85, the correlation between a perfectly measured value and one draw is bounded near sqrt(0.85) ~ 0.92.
**So the 0.90 floor sits about 0.02 below the theoretical maximum**, and passing it is close to the best
any recomputation could do.

P1's reliability question is untouched by all of this: it had not been computed when the correction was
made, and it is not what any number above measures.
"""

from __future__ import annotations

import csv
import glob
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.verifier.stats import auc, logit_fit, predict_proba, spearman           # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
TRIALS = os.path.join(RESULTS, "eegmmidb_trials.csv")
TRIAL_SHARDS = os.path.join(RESULTS, "eegmmidb_trials.*.csv")
LABELS = {"imagery": os.path.join(RESULTS, "eegmmidb_bci.csv"),
          "executed": os.path.join(RESULTS, "eegmmidb_bci_executed.csv")}
OUT = os.path.join(RESULTS, "e38_bci_label_reliability.json")

N_FEATURES = 6
N_SPLITS = 200
MIN_TRIALS_PER_CLASS_HALF = 6
MIN_SUBJECTS = 60
MIN_AGREEMENT = 0.90
N_G1_DRAWS = 9
MAX_MEDIAN_DIFF = 0.05
FOLDS = 5
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _load_trials():
    paths = [TRIALS] if os.path.exists(TRIALS) else sorted(glob.glob(TRIAL_SHARDS))
    by = {}
    for p in paths:
        for r in csv.DictReader(open(p, newline="")):
            key = (r["subject"], r["task"])
            by.setdefault(key, {"X": [], "y": []})
            by[key]["X"].append([_f(r[f"f{i}"]) for i in range(N_FEATURES)])
            by[key]["y"].append(_f(r["y"]))
    out = {}
    for k, v in by.items():
        X = np.asarray(v["X"], float)
        y = np.asarray(v["y"], float)
        ok = np.isfinite(X).all(axis=1) & np.isfinite(y)
        out[k] = (X[ok], y[ok])
    return out, paths


def _auc_folds(X, y, rng, folds=FOLDS):
    """The builder's own out-of-fold estimator, reproduced for G1 only."""
    n = len(y)
    if np.unique(y).size < 2:
        return float("nan")
    order = rng.permutation(n)
    fold = np.empty(n, int)
    fold[order] = np.arange(n) % folds
    pred = np.full(n, np.nan)
    for k in range(folds):
        te, tr = fold == k, fold != k
        if np.unique(y[tr]).size < 2 or te.sum() == 0:
            continue
        mu, sd = X[tr].mean(axis=0), X[tr].std(axis=0)
        sd[sd == 0] = 1.0
        Xtr = np.column_stack([np.ones(int(tr.sum())), (X[tr] - mu) / sd])
        Xte = np.column_stack([np.ones(int(te.sum())), (X[te] - mu) / sd])
        try:
            pred[te] = predict_proba(Xte, logit_fit(Xtr, y[tr]))
        except Exception:                                                  # noqa: BLE001
            continue
    ok = np.isfinite(pred)
    return float(auc(y[ok], pred[ok])) if ok.sum() > 4 else float("nan")


def _auc_loo(X, y):
    """Leave-one-out AUC. Deterministic, and the declared within-half estimator."""
    n = len(y)
    if np.unique(y).size < 2 or n < 6:
        return float("nan")
    pred = np.full(n, np.nan)
    for i in range(n):
        tr = np.ones(n, bool)
        tr[i] = False
        if np.unique(y[tr]).size < 2:
            continue
        mu, sd = X[tr].mean(axis=0), X[tr].std(axis=0)
        sd[sd == 0] = 1.0
        Xtr = np.column_stack([np.ones(int(tr.sum())), (X[tr] - mu) / sd])
        Xte = np.concatenate([[1.0], (X[i] - mu) / sd]).reshape(1, -1)
        try:
            pred[i] = predict_proba(Xte, logit_fit(Xtr, y[tr]))[0]
        except Exception:                                                  # noqa: BLE001
            continue
    ok = np.isfinite(pred)
    return float(auc(y[ok], pred[ok])) if ok.sum() > 4 else float("nan")


def _split_half(X, y, rng, cap=None):
    """One stratified split into two disjoint halves; returns their two LOO AUCs, or (nan, nan)."""
    idx0 = np.flatnonzero(y == 0)
    idx1 = np.flatnonzero(y == 1)
    rng.shuffle(idx0)
    rng.shuffle(idx1)
    if cap is not None:
        idx0, idx1 = idx0[:2 * cap], idx1[:2 * cap]
    h0 = min(len(idx0) // 2, len(idx1) // 2)
    if h0 < MIN_TRIALS_PER_CLASS_HALF:
        return float("nan"), float("nan")
    a = np.concatenate([idx0[:h0], idx1[:h0]])
    b = np.concatenate([idx0[h0:2 * h0], idx1[h0:2 * h0]])
    return _auc_loo(X[a], y[a]), _auc_loo(X[b], y[b])


def _reliability(data, task, rng, permute=False, cap=None, n_splits=N_SPLITS):
    """Mean split-half Spearman across `n_splits` random splits, plus the per-split subject matrices."""
    subs = sorted(s for (s, t) in data if t == task)
    prepared = []
    for s in subs:
        X, y = data[(s, task)]
        if permute:
            y = rng.permutation(y)
        prepared.append((s, X, y))
    rs, A, B = [], [], []
    for _ in range(n_splits):
        a_, b_ = [], []
        for _s, X, y in prepared:
            u, v = _split_half(X, y, rng, cap=cap)
            a_.append(u)
            b_.append(v)
        a_, b_ = np.asarray(a_, float), np.asarray(b_, float)
        ok = np.isfinite(a_) & np.isfinite(b_)
        if ok.sum() < MIN_SUBJECTS:
            continue
        r = spearman(a_[ok], b_[ok])
        if np.isfinite(r):
            rs.append(r)
            A.append(a_)
            B.append(b_)
    if not rs:
        return None
    r = float(np.mean(rs))
    sb = 2 * r / (1 + r) if r > -1 else float("nan")
    return {"subjects": subs, "r_half": r, "r_sb": float(sb),
            "ceiling": float(np.sqrt(sb)) if sb > 0 else 0.0,
            "n_splits_used": len(rs), "A": np.asarray(A), "B": np.asarray(B)}


def _boot_ci(res, rng, reps=600):
    """Subject-level bootstrap of the split-averaged reliability."""
    A, B = res["A"], res["B"]
    n = A.shape[1]
    vals = []
    for _ in range(reps):
        pick = rng.integers(0, n, n)
        rr = []
        for k in range(A.shape[0]):
            a_, b_ = A[k][pick], B[k][pick]
            ok = np.isfinite(a_) & np.isfinite(b_)
            if ok.sum() >= MIN_SUBJECTS:
                v = spearman(a_[ok], b_[ok])
                if np.isfinite(v):
                    rr.append(v)
        if rr:
            m = float(np.mean(rr))
            vals.append(2 * m / (1 + m) if m > -1 else np.nan)
    vals = np.asarray([v for v in vals if np.isfinite(v)], float)
    if vals.size < 30:
        return float("nan"), float("nan")
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def main(argv=None) -> int:
    print("E38 — split-half reliability of E28's per-subject BCI label")
    print("   Reads NO resting-state candidate. This file can only characterise a label.")
    data, paths = _load_trials()
    if not data:
        print(f"\n   *** no trial cache found ({os.path.basename(TRIALS)} or shards).")
        return 2
    rng = np.random.default_rng(SEED)
    st = {"experiment": "E38", "trial_files": [os.path.basename(p) for p in paths]}

    print("\n" + "=" * 100)
    print("G1 — RULE-20 GATE: does the trial cache reproduce the stored label?")
    print("=" * 100)
    stored = {}
    for r in csv.DictReader(open(LABELS["imagery"], newline="")):
        if r["status"] == "ok":
            stored[r["subject"]] = _f(r["imagery_auc"])
    subs = sorted(s for (s, t) in data if t == "imagery" and s in stored)
    re_, st_ = [], []
    for s in subs:
        X, y = data[(s, "imagery")]
        draws = [_auc_folds(X, y, rng) for _ in range(N_G1_DRAWS)]
        draws = [d for d in draws if np.isfinite(d)]
        if draws:
            re_.append(float(np.mean(draws)))
            st_.append(stored[s])
    re_, st_ = np.asarray(re_), np.asarray(st_)
    agree = spearman(re_, st_) if re_.size > 5 else float("nan")
    mdiff = float(np.median(np.abs(re_ - st_))) if re_.size else float("nan")
    print(f"   subjects in both the cache and the label table : {re_.size}   (floor {MIN_SUBJECTS})")
    print(f"   Spearman(recomputed, stored)                   : {agree:.4f}   (floor {MIN_AGREEMENT})")
    print(f"   median |recomputed - stored|                   : {mdiff:.4f}   (ceiling {MAX_MEDIAN_DIFF})")
    print(f"   Recomputed value is the mean of {N_G1_DRAWS} independent fold draws; the stored value is one\n   draw, so ~0.92 is the theoretical ceiling for this comparison. See the header correction.")
    g1 = bool(re_.size >= MIN_SUBJECTS and np.isfinite(agree)
              and agree >= MIN_AGREEMENT and mdiff <= MAX_MEDIAN_DIFF)
    print(f"\n   G1 {'PASSED' if g1 else '*** FAILED'}")
    st["g1"] = {"n": int(re_.size), "agreement": float(agree), "median_diff": mdiff, "passed": g1}
    if not g1:
        print("   The cache is not the quantity the label was built from. ABSENT, not negative (rule 31).")
        json.dump(st, open(OUT, "w"), indent=2, default=float)
        return 1

    print("\n" + "=" * 100)
    print("P1 — THE PRIMARY: split-half reliability of the IMAGERY label")
    print("=" * 100)
    res = _reliability(data, "imagery", rng)
    if res is None:
        print("   too few subjects survive splitting. ABSENT.")
        json.dump(st, open(OUT, "w"), indent=2, default=float)
        return 1
    lo, hi = _boot_ci(res, rng)
    print(f"   subjects                          : {len(res['subjects'])}")
    print(f"   splits used                       : {res['n_splits_used']} of {N_SPLITS}")
    print(f"   r_half  (two disjoint halves)     : {res['r_half']:+.4f}")
    print(f"   r_sb    (Spearman-Brown, full)    : {res['r_sb']:+.4f}   [{lo:+.4f}, {hi:+.4f}]")
    print(f"   ceiling (sqrt of reliability)     : {res['ceiling']:.4f}")
    viable = bool(np.isfinite(lo) and lo > 0)
    print(f"\n   P1: the label is {'VIABLE as a per-subject target' if viable else 'NOT VIABLE'}")
    st["p1"] = {"r_half": res["r_half"], "r_sb": res["r_sb"], "ci": [lo, hi],
                "ceiling": res["ceiling"], "n_subjects": len(res["subjects"]),
                "n_splits_used": res["n_splits_used"], "viable": viable}

    print("\n" + "=" * 100)
    print("P2 — THE COMPARISON ARM: the same for EXECUTED movement")
    print("=" * 100)
    res_e = _reliability(data, "executed", rng)
    if res_e is None:
        print("   executed arm unavailable — reported as absent, not as a null.")
        st["p2"] = None
    else:
        lo_e, hi_e = _boot_ci(res_e, rng)
        print(f"   subjects {len(res_e['subjects'])}   r_half {res_e['r_half']:+.4f}   "
              f"r_sb {res_e['r_sb']:+.4f} [{lo_e:+.4f}, {hi_e:+.4f}]   ceiling {res_e['ceiling']:.4f}")
        st["p2"] = {"r_half": res_e["r_half"], "r_sb": res_e["r_sb"], "ci": [lo_e, hi_e],
                    "ceiling": res_e["ceiling"], "n_subjects": len(res_e["subjects"])}
        e_viable = bool(np.isfinite(lo_e) and lo_e > 0)
        if e_viable and not viable:
            print("   READING: the deposit supports per-subject labels; IMAGERY specifically is too weak.")
        elif not e_viable and not viable:
            print("   READING: 45 trials is too few for ANY per-subject label here, imagery or executed.")
        elif viable:
            print("   READING: both arms carry reliable between-subject variance.")

    print("\n" + "=" * 100)
    print("P3 — PLACEBO: the same estimator on a destroyed label")
    print("=" * 100)
    if not viable:
        print("   NOT INFORMATIVE: P1's interval includes zero, so there is no real reliability for a")
        print("   destroyed label to fail to reproduce (rule 48, which E37 produced).")
        st["p3"] = {"status": "not_informative"}
        p3 = None
    else:
        res_p = _reliability(data, "imagery", rng, permute=True, n_splits=max(40, N_SPLITS // 4))
        if res_p is None:
            print("   placebo could not be computed — reported, not silently dropped.")
            st["p3"] = {"status": "uncomputable"}
            p3 = None
        else:
            lo_p, hi_p = _boot_ci(res_p, rng, reps=300)
            print(f"   permuted-label r_sb {res_p['r_sb']:+.4f} [{lo_p:+.4f}, {hi_p:+.4f}]   "
                  f"real {res['r_sb']:+.4f}")
            p3 = bool(res["r_sb"] > res_p["r_sb"] and not (np.isfinite(lo_p) and lo_p > 0))
            print(f"   P3 {'PASSED' if p3 else '*** FAILED — the estimator manufactures agreement'}")
            st["p3"] = {"r_sb": res_p["r_sb"], "ci": [lo_p, hi_p], "passed": p3}

    print("\n" + "=" * 100)
    print("P4 — REPORTED CONTEXT: reliability against trials per half")
    print("=" * 100)
    st["p4"] = {}
    for cap in (8, 11, 15, 22):
        r_ = _reliability(data, "imagery", rng, cap=cap, n_splits=max(40, N_SPLITS // 4))
        if r_ is None:
            print(f"   {cap:3d} trials per class available   — too few subjects survive; not reported")
            continue
        st["p4"][cap] = {"r_half": r_["r_half"], "r_sb": r_["r_sb"]}
        print(f"   {cap:3d} trials per class available   r_half {r_['r_half']:+.4f}   "
              f"r_sb {r_['r_sb']:+.4f}")

    print("\n" + "=" * 100)
    print("VERDICT")
    print("=" * 100)
    if p3 is False:
        verdict = "not_interpretable_placebo"
        print("   NOT INTERPRETABLE: the estimator manufactures agreement on a destroyed label.")
    elif not viable:
        verdict = "label_not_viable"
        print("   LABEL NOT VIABLE: the imagery label carries no reliable between-subject variance.")
        print("   Challenge B's healthy-BCI substitution cannot be run on this deposit as E28 designed it.")
        print("   This is a fact about the LABEL, not a negative about any EEG feature.")
    else:
        verdict = "label_viable"
        print(f"   LABEL VIABLE. Any resting feature is bounded at |rho| <= {res['ceiling']:.3f} by")
        print("   attenuation alone. A successor to E28 must state that ceiling in its own header.")
    st["verdict"] = verdict
    json.dump(st, open(OUT, "w"), indent=2, default=float)
    print(f"\n   wrote results/{os.path.basename(OUT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
