"""E175 — E172's effect in a DIFFERENT deposit, a different paradigm and 104 different subjects.

REGISTERED BEFORE `results/eegmmidb_pretrial*.csv` CONTAINS A COMPLETE SHARD. The extractor was written and
committed in the same change; a 90-trial smoke test on one subject confirmed the table's shape and nothing
else has been read.

=========================================================================================================
THE CLAIM UNDER TEST, AND WHY THIS IS THE TEST THAT MATTERS
=========================================================================================================
E172: on Stieger's online BCI, pre-cue alpha amplitude is higher on the successful member of a matched
adjacent hit/miss pair — `mu_mean` **0.5176 [0.5054, 0.5303]**, p = 0.0060, placebo clean, above a
measured floor of rho = 0.05. E174 asks whether that survives a change of recording day in the same
subjects. **Neither answers the question a clinical claim needs**, which is whether the effect exists
outside one deposit.

eegmmidb differs on every axis that matters: 104 different subjects, 64 channels at 160 Hz instead of 62
at 1000 Hz, a different laboratory and decade, and — most importantly — **a different paradigm**.
Stieger's subjects control a cursor with continuous visual feedback; eegmmidb's imagine a movement with
none. If the effect is a property of feedback, engagement with a moving cursor, or Stieger's particular
task, it should not appear here.

=========================================================================================================
THE OUTCOME VARIABLE IS DIFFERENT AND THAT IS DELIBERATE, NOT A COMPROMISE
=========================================================================================================
eegmmidb has no behavioural readout, so "was the command followed" must become **"was the covert command
LEGIBLE in this trial"**: did a subject-level cross-validated decoder classify this trial's imagined
movement correctly? Per-trial correctness comes from a 5-fold logistic on the post-cue mu/beta features
the deposit's own label was built from (`f0..f5`, imported unchanged), with **folds over TRIALS and the
pre-cue features playing no part in the decoder** — so the label cannot see the predictor.

**This is closer to the covert-consciousness construct than Stieger's cursor is**, and saying so before the
result is the point. A bedside assessment of an unresponsive patient has no behavioural readout either; it
asks exactly whether the command response is detectable in this attempt. A positive here would therefore
generalise the claim in the direction the flagship application needs, and a null would bound it to
paradigms with feedback.

=========================================================================================================
DESIGN — E172's, UNCHANGED WHERE IT CAN BE
=========================================================================================================
Same matched-pair construction (each correct trial paired with the nearest incorrect one within
`MAX_GAP = 5`), same statistic (fraction of pairs with the larger feature on the correct member), same
exact within-pair flip null, same cluster bootstrap over SUBJECTS, same candidate list, same ladder.
`_spectral` and the pre-cue window are imported from the Stieger extractor, so the features are the same
computation and not merely the same name (rule 20).

**ONE-SIDED in E172's direction**, declared here: the direction is no longer open. A reversal is
enumerated as its own verdict below and is not a partial success.

PRIMARY    `mu_mean`, as in E172.
INCUMBENT  the decoder's own confidence on the trial (|predicted probability - 0.5|), scored identically.
           It is the trivially available non-spontaneous predictor of trial legibility, and it is the bar
           (rule 45). E172's incumbent was unavailable because its artefact flag was constant; this one
           is not, so the comparison E172 could not make is made here.

=========================================================================================================
GATES
=========================================================================================================
G1  >= 60 subjects with >= 20 pairs. eegmmidb gives ~45 trials per subject per task against Stieger's 450,
    so the per-subject pair count is an order of magnitude smaller and the floor is set from what the
    deposit can supply rather than copied from E172 (rule 63).
G2  **THE DECODER MUST BE ALIVE (rule 53).** Pooled out-of-fold decoding accuracy must beat its own
    within-subject label permutation. If the decoder is at chance, "correct" is a coin flip, there is no
    legibility to predict, and a null would be uninterpretable — this is E61's trap and E33's rule.
G3  (a) trial index scored as a candidate must be at chance and the pairing directionally balanced;
    (b) an i.i.d. noise feature must NOT be detected; (c) a ladder gives the measured floor, and no
    detected rung means every null is ABSENT rather than negative (rule 31).

=========================================================================================================
VERDICT — FAILING AND WRONG-DIRECTION CASES FIRST (rules 31, 37)
=========================================================================================================
  (1) NOT INTERPRETABLE  G1, G2 or G3(a)/(b) fails.
  (2) NO POWER           G3(c) detects nothing; the deposit's ~45 trials per subject cannot resolve an
                         effect of E172's size and the comparison is not available.
  (3) REVERSED           the primary excludes 0.5 on the opposite side. Then the effect is
                         paradigm-dependent with a sign flip, which is a stronger statement than a null
                         and would require both results to be re-examined.
  (4) NOT REPLICATED     one-sided p > 0.05 with a floor established. The effect is bounded to Stieger's
                         paradigm, and E172 carries that bound from here on.
  (5) REPLICATED         one-sided p <= 0.05, direction as E172's, and the effect survives comparison
                         against the decoder-confidence incumbent.

REGISTERED PREDICTION: **(2) or (4).** E172's effect is 1.8 percentage points on 6,413 pairs; eegmmidb
offers roughly 45 trials per subject over 104 subjects, so perhaps 1,500-2,000 pairs, and the measured
floor is likely to sit above the effect. **The most probable honest outcome of this file is that it lacks
the power to decide**, which is why G3(c) exists and why NO POWER is enumerated before NOT REPLICATED —
the two must not be reported as the same thing.

    python bsde/src/bsde/experiments/e175_external_replication_eegmmidb.py
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
sys.path.insert(0, HERE)

import e172_matched_pair_trial_responsiveness as E172                          # noqa: E402
from bsde.verifier.stats import auc, logit_fit, predict_proba, screen_candidates  # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e175_external_replication_eegmmidb.json")
SEED = 20260801

POST = [f"f{i}" for i in range(6)]
CANDIDATES = list(E172.CANDIDATES)
PRIMARY = E172.PRIMARY
INCUMBENT = "decoder_confidence"
MAX_GAP = E172.MAX_GAP
MIN_PAIRS = 20
MIN_SUBJECTS = 60
FOLDS = 5
ALPHA = 0.05
Q = 0.05
E172_DIRECTION = 1


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def decode(X, y, rng, folds=FOLDS):
    """Out-of-fold predicted probability from a logistic on the POST-cue features only.

    Folds are over TRIALS within the subject, and the pre-cue features are not in `X`, so the correctness
    label cannot see the predictor it will later be regressed on.
    """
    n = len(y)
    order = rng.permutation(n)
    fold = np.empty(n, int)
    fold[order] = np.arange(n) % folds
    p = np.full(n, np.nan)
    A = np.column_stack([np.ones(n), X])
    for k in range(folds):
        te, tr = fold == k, fold != k
        if te.sum() == 0 or len(np.unique(y[tr])) < 2:
            continue
        try:
            b = logit_fit(A[tr], y[tr])
            p[te] = predict_proba(A[te], b)
        except Exception:                                                  # noqa: BLE001
            continue
    return p


def build():
    rows, seen = [], set()
    for path in sorted(glob.glob(os.path.join(RESULTS, "eegmmidb_pretrial*.csv"))):
        if os.path.getsize(path) == 0:
            continue
        for r in csv.DictReader(open(path, newline="")):
            k = (r["subject"], r["run"], r["trial"])
            if k in seen:
                continue
            seen.add(k)
            rows.append(r)
    by = {}
    for r in rows:
        by.setdefault(r["subject"], []).append(r)
    rng = np.random.default_rng(SEED)
    sess, pooled_y, pooled_p = [], [], []
    for sub, rr in sorted(by.items()):
        rr.sort(key=lambda r: (r["run"], int(float(r["trial"]))))
        y = np.array([_f(r["y"]) for r in rr])
        X = np.array([[_f(r[c]) for c in POST] for r in rr], float)
        ok = np.isfinite(y) & np.all(np.isfinite(X), axis=1)
        if ok.sum() < 20 or len(np.unique(y[ok])) < 2:
            continue
        p = decode(X[ok], y[ok], rng)
        correct = np.full(len(rr), np.nan)
        conf = np.full(len(rr), np.nan)
        idx = np.flatnonzero(ok)
        good = np.isfinite(p)
        correct[idx[good]] = ((p[good] >= 0.5).astype(float) == y[ok][good]).astype(float)
        conf[idx[good]] = np.abs(p[good] - 0.5)
        pooled_y.append(y[ok][good])
        pooled_p.append(p[good])
        pairs = E172.make_pairs(correct, max_gap=MAX_GAP)
        if len(pairs) < MIN_PAIRS:
            continue
        cols = {c: np.array([_f(r.get(c, "")) for r in rr]) for c in CANDIDATES}
        cols[INCUMBENT] = conf
        cols["_index"] = np.arange(len(rr), dtype=float)
        sess.append({"subject": sub, "session": "0", "pairs": pairs, "cols": cols,
                     "n_trials": len(rr), "y": y, "correct": correct})
    return sess, len(rows), (np.concatenate(pooled_y) if pooled_y else np.array([])), \
        (np.concatenate(pooled_p) if pooled_p else np.array([]))


def one_sided_p(sess, name, rng, reps=E172.REPS):
    obs = E172.frac_stat(sess, name)["mean"]
    if not np.isfinite(obs):
        return obs, float("nan")
    nulls = []
    for _ in range(reps):
        flips = [rng.integers(0, 2, len(s["pairs"])).astype(bool) for s in sess]
        v = E172.frac_stat(sess, name, flips=flips)["mean"]
        if np.isfinite(v):
            nulls.append(v)
    if len(nulls) < 30:
        return obs, float("nan")
    n = np.asarray(nulls)
    return obs, float((n >= obs).mean() if E172_DIRECTION > 0 else (n <= obs).mean())


def main() -> int:
    print("E175 — E172's effect in eegmmidb: different deposit, paradigm, montage and subjects")
    sess, n_rows, py, pp = build()
    res = {"experiment": "E175", "n_trial_rows": n_rows, "e172_primary": 0.5176}
    if not sess:
        print("   ABSENT: the eegmmidb pre-trial extraction has produced nothing usable yet.")
        json.dump(res, open(OUT, "w"), indent=2)
        return 2
    subs = sorted({s["subject"] for s in sess})
    npairs = [len(s["pairs"]) for s in sess]
    res.update({"n_subjects": len(subs), "total_pairs": int(sum(npairs)),
                "median_pairs": float(np.median(npairs))})
    res["G1_pass"] = bool(len(subs) >= MIN_SUBJECTS)
    print(f"   {n_rows} trial rows -> {len(subs)} subjects, {sum(npairs)} pairs "
          f"(median {np.median(npairs):.0f})")
    print(f"   G1 {'PASS' if res['G1_pass'] else '*** FAIL'} (floor {MIN_SUBJECTS} subjects, "
          f"{MIN_PAIRS} pairs each)")
    if not res["G1_pass"]:
        res["verdict"] = "NOT-INTERPRETABLE"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    rng = np.random.default_rng(SEED)
    acc = float(np.mean((pp >= 0.5).astype(float) == py))
    a = float(auc(py.astype(int), pp))
    nulls = []
    for _ in range(200):
        nulls.append(float(np.mean((pp >= 0.5).astype(float) == rng.permutation(py))))
    nn = np.asarray(nulls)
    g2 = acc > float(np.quantile(nn, 0.95))
    res["G2_decoder"] = {"accuracy": acc, "auc": a, "null_p95": float(np.quantile(nn, 0.95)),
                         "pass": bool(g2)}
    print(f"   G2 decoder alive: pooled out-of-fold accuracy {acc:.4f} (AUC {a:.4f}) vs permuted "
          f"p95 {np.quantile(nn, 0.95):.4f}   {'PASS' if g2 else '*** FAIL'}")
    if not g2:
        res["verdict"] = "NOT-INTERPRETABLE"
        res["why"] = ("the decoder is at chance, so 'correct' is a coin flip and there is no legibility "
                      "to predict (rule 53)")
        print("\n   VERDICT NOT INTERPRETABLE — " + res["why"])
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    gaps = np.concatenate([[h - m for (h, m) in s["pairs"]] for s in sess]).astype(float)
    signed = float(gaps.mean())
    gnull = np.asarray([float((gaps * np.where(rng.integers(0, 2, gaps.size) > 0, -1, 1)).mean())
                        for _ in range(2000)])
    lo, hi = float(np.quantile(gnull, 0.025)), float(np.quantile(gnull, 0.975))
    idx_over = {(s["subject"], s["session"]): s["cols"]["_index"] for s in sess}
    io_obs, io_p, _, _ = E172.flip_null(sess, PRIMARY, np.random.default_rng(SEED + 2), reps=1000,
                                        override=idx_over)
    g3a = (lo <= signed <= hi) and np.isfinite(io_p) and io_p > ALPHA
    res["G3a"] = {"signed_gap": signed, "null": [lo, hi], "index_mean": float(io_obs),
                  "index_p": float(io_p), "pass": bool(g3a)}
    print(f"   G3(a) signed gap {signed:+.4f} in [{lo:+.4f}, {hi:+.4f}]; trial index {io_obs:.4f}, "
          f"p = {io_p:.4f}   {'PASS' if g3a else '*** FAIL'}")
    _, p0, _, _ = E172.flip_null(sess, PRIMARY, np.random.default_rng(SEED + 3), reps=1000,
                                 override=E172.synthetic(sess, 0.0, rng))
    g3b = np.isfinite(p0) and p0 > ALPHA
    res["G3b"] = {"p": float(p0), "pass": bool(g3b)}
    print(f"   G3(b) i.i.d. noise p = {p0:.4f}   {'PASS' if g3b else '*** FAIL'}")
    if not (g3a and g3b):
        res["verdict"] = "NOT-INTERPRETABLE"
        res["why"] = "the pairing or the null did not behave"
        print("\n   VERDICT NOT INTERPRETABLE — " + res["why"])
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    floor, ladder = None, []
    for rho in E172.RUNGS:
        _, p, _, _ = E172.flip_null(sess, PRIMARY, np.random.default_rng(SEED + 4), reps=1000,
                                    override=E172.synthetic(sess, rho, rng))
        ladder.append({"rho": rho, "p": float(p)})
        print(f"   G3(c) rho = {rho:.2f}: p = {p:.4f}")
        if np.isfinite(p) and p <= ALPHA:
            floor = rho
            break
    res["ladder"], res["floor"] = ladder, floor
    print(f"   FLOOR: {'none' if floor is None else '%.2f' % floor}")

    pool = {c: np.concatenate([s["cols"][c] for s in sess]) for c in CANDIDATES}
    usable, dropped = screen_candidates(pool)
    for c, why in dropped.items():
        print(f"   dropped: {c} ({why})")
    names = [c for c in CANDIDATES if c in usable] + [INCUMBENT]
    print(f"\n   {'candidate':<24s} {'frac':>8s} {'[95% CI]':>20s} {'same side':>10s} {'p(1-sided)':>11s}")
    table, ps = {}, []
    for c in names:
        st = E172.frac_stat(sess, c)
        obs, p = one_sided_p(sess, c, np.random.default_rng(SEED + 11))
        lo_, hi_ = E172.cluster_ci(st, np.random.default_rng(SEED + 12))
        table[c] = {"mean": st["mean"], "ci": [lo_, hi_], "frac_same_side": st["frac_same_side"],
                    "p_one_sided": float(p)}
        if c != INCUMBENT:
            ps.append(p)
        print(f"   {c:<24s} {st['mean']:>8.4f} [{lo_:>8.4f},{hi_:>8.4f}] "
              f"{st['frac_same_side']:>10.2f} {p:>11.4f}"
              + ("   <- INCUMBENT" if c == INCUMBENT else ""))
    keep = E172.bh(ps, q=Q)
    cn = [c for c in names if c != INCUMBENT]
    res["table"], res["survivors_bh"] = table, [cn[i] for i in sorted(keep)]
    print(f"   BH q={Q}: {res['survivors_bh'] or 'none'}")

    prim = table[PRIMARY]
    if floor is None:
        v, why = "NO-POWER", ("no injected within-pair effect is detectable at this deposit's ~45 trials "
                              "per subject, so a null here is ABSENT and not a failure to replicate")
    elif np.isfinite(prim["ci"][1]) and prim["ci"][1] < 0.5:
        v, why = "REVERSED", ("the primary excludes 0.5 on the side opposite to E172's: the effect is "
                              "paradigm-dependent with a sign flip and both results need re-examining")
    elif not (np.isfinite(prim["p_one_sided"]) and prim["p_one_sided"] <= ALPHA):
        v, why = "NOT-REPLICATED", (f"one-sided p = {prim['p_one_sided']:.4f} with a floor of "
                                    f"rho = {floor:.2f}; the effect is bounded to Stieger's paradigm and "
                                    "E172 carries that bound from here on")
    elif np.isfinite(prim["frac_same_side"]) and prim["frac_same_side"] < 0.5:
        v, why = "NOT-CLAIMED", "fewer than half the subjects fall on the mean's side of 0.5"
    else:
        v, why = "REPLICATED", (f"{prim['mean']:.4f}, one-sided p = {prim['p_one_sided']:.4f}, in a "
                                "different deposit, paradigm, montage and subject sample, against a "
                                "decoder-legibility outcome with no behavioural readout — the construct "
                                "the covert-consciousness application needs")
    res["verdict"], res["why"] = v, why
    print(f"\n   VERDICT {v} — {why}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
