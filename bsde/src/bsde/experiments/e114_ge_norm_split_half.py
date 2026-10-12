"""E114 -- Does `ge_norm` predict BOTH independent halves of BCI accuracy? An internal replication E86 had
available and never used.

REGISTERED BEFORE ANY SPLIT-HALF CORRELATION IS COMPUTED. Existing tables only.

=========================================================================================================
WHY THIS IS WORTH RUNNING WHILE THE EXTERNAL REPLICATION IS BLOCKED
=========================================================================================================
E86's `ge_norm` -> accuracy association (D1 rho +0.3069 [+0.0495, +0.5343]) has survived three challenges:
E97 (trait-like, so the null change-score is expected), E101 (UNDETERMINED -- the trait model is not
separable from noise at n = 61), E106 (not alpha frequency: rho(ge_norm, iaf) = +0.0781, partials +0.2837
and +0.2423). **Its surviving qualification is multiplicity, BH q = 0.0920**, and the only fix is an
independent test -- which E108 attempted and could not run, because eegmmidb's decodability label was not
alive (16.3 % of subjects above their own permutation null against a 20 % floor).

While the CSP rebuild of that outcome runs, there is a cheaper independent test sitting unused in the
data: **`stieger_labels.csv` ships `accuracy_odd` and `accuracy_even`** -- the same subject's control
accuracy computed on disjoint halves of their trials. E86 used only the pooled `accuracy`.

Two halves of one measurement are not a new cohort and this is NOT a substitute for E108. What it IS: a
test that a real association must pass and a spurious one need not. **If `ge_norm` tracks a genuine
property of a subject's BCI control, it must predict both halves; if it tracks noise in the pooled score,
it can predict the pooled value while failing each half.** The halves share subject, session, montage and
day -- so this cannot address multiplicity, and saying so is the point of this paragraph.

=========================================================================================================
ESTIMAND
=========================================================================================================
Subject means over sessions, exactly as E86 computed them, n = 62.

    A  spearman( ge_norm , accuracy_odd )
    B  spearman( ge_norm , accuracy_even )

    P  the CONJUNCTION: both intervals must exclude zero, in the SAME (positive) direction.

**And the size is predicted, not merely the sign.** Each half carries about half the trials, so its
reliability is lower and the observed correlation is attenuated by sqrt(rel_half / rel_full). By
Spearman-Brown with the pooled score's split-half reliability r_sh (computed here from the two halves
themselves), rel_half / rel_full = (1 + r_sh) / 2 ... expressed the usable way round:

    predicted_half = observed_pooled * sqrt( 2 * r_sh / (1 + r_sh) ) ** -1

is the WRONG direction, so it is written out explicitly in code rather than in prose to avoid inverting it
here. The quantity reported is: observed half-correlations against the value the pooled correlation
predicts for them under a pure attenuation model, using the measured split-half reliability of accuracy.
**A half-correlation far BELOW that prediction is the failure mode this experiment exists to detect.**

VERDICT, wrong direction FIRST (rule 37):

    (a) NEITHER half's interval excludes 0 -> FAILS SPLIT-HALF. The pooled association does not appear in
        either half of the very measurement it is about. That is strong evidence the pooled result is
        noise, and E86 would need re-describing.
    (b) exactly ONE half excludes 0 -> INCONSISTENT. Halves of one measurement should behave alike; one
        surviving and one not is what a marginal effect looks like and must be reported as instability,
        not as partial support.
    (c) BOTH exclude 0 but both sit far below the attenuation prediction -> PASSES SIGN, FAILS SIZE.
    (d) BOTH exclude 0 and both are consistent with the attenuation prediction -> PASSES. E86 clears a
        test it could have failed, without addressing multiplicity.

PREDICTED: (d) at ~45 %, (b) at ~25 %, (c) at ~20 %, (a) at ~10 %.

=========================================================================================================
GATES
=========================================================================================================
    G1  COVERAGE. >= 50 subjects with `ge_norm`, `accuracy_odd` and `accuracy_even` all finite.
    G2  THE HALVES MUST BE HALVES. Their split-half correlation must be positive and substantial -- if
        `accuracy_odd` and `accuracy_even` do not agree with each other, they are not two measurements of
        one thing and no conjunction over them means anything. Reported with a Spearman-Brown corrected
        reliability, and the attenuation prediction is built from it.
    G3  THE POOLED EFFECT MUST BE PRESENT HERE. E86's D1 is recomputed on this subset and must reproduce;
        otherwise the split-half test is being applied to something that is not E86's result (rule 31).
    G4  NOT DRIVEN BY ONE SUBJECT. Leave-one-subject-out over the pooled correlation; the largest single
        deletion effect is reported. This does not gate the verdict -- it is reported because E86's
        interval is wide and a reader should be able to see whether one point carries it.

PLACEBO: accuracy halves permuted across subjects (the SAME permutation applied to both halves, so their
mutual agreement is preserved and only the link to `ge_norm` is destroyed), 2000 draws. Primary read FIRST
(rule 48).

SCOPE. Stieger BCI, 62 subjects. This is an internal consistency test and explicitly NOT an external
replication; it cannot and does not address the BH q = 0.0920 qualification.
"""
from __future__ import annotations

import csv
import json
import os
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
GRAPH = os.path.join(RESULTS, "stieger_graph62.csv")
ACC = os.path.join(RESULTS, "stieger_labels.csv")
OUT = os.path.join(RESULTS, "e114_ge_norm_split_half.json")

PRIMARY = "ge_norm"
MIN_SUBJECTS = 50
REPS = 4000
PLACEBO_DRAWS = 2000
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _rank(x):
    return np.argsort(np.argsort(np.asarray(x, float))).astype(float)


def spearman(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 5 or np.ptp(x[ok]) <= 0 or np.ptp(y[ok]) <= 0:
        return float("nan")
    rx, ry = _rank(x[ok]), _rank(y[ok])
    rx -= rx.mean(); ry -= ry.mean()
    d = float(np.sqrt((rx ** 2).sum() * (ry ** 2).sum()))
    return float((rx * ry).sum() / d) if d > 1e-12 else float("nan")


def ci(v):
    v = np.sort(np.asarray([q for q in v if np.isfinite(q)], float))
    if v.size < 50:
        return float("nan"), float("nan")
    return float(np.quantile(v, .025)), float(np.quantile(v, .975))


def main() -> int:
    for p in (GRAPH, ACC):
        if not os.path.exists(p):
            print(f"ABSENT: {p}")
            return 2
    lab = defaultdict(list)
    for r in csv.DictReader(open(ACC, newline="")):
        lab[r["subject"]].append(r)
    graph = defaultdict(list)
    for r in csv.DictReader(open(GRAPH, newline="")):
        graph[r["subject"]].append(r)

    subs, g, apool, aodd, aeven = [], [], [], [], []
    for s in sorted(set(graph) & set(lab)):
        gv = np.nanmean([_f(r.get(PRIMARY, "")) for r in graph[s]])
        p = np.nanmean([_f(r.get("accuracy", "")) for r in lab[s]])
        o = np.nanmean([_f(r.get("accuracy_odd", "")) for r in lab[s]])
        e = np.nanmean([_f(r.get("accuracy_even", "")) for r in lab[s]])
        if all(np.isfinite(x) for x in (gv, p, o, e)):
            subs.append(s); g.append(gv); apool.append(p); aodd.append(o); aeven.append(e)
    g = np.array(g); apool = np.array(apool); aodd = np.array(aodd); aeven = np.array(aeven)
    n = g.size
    res = {"n_subjects": n, "gates": {}}
    print(f"{n} subjects with ge_norm, pooled accuracy and both halves")
    res["gates"]["G1_pass"] = bool(n >= MIN_SUBJECTS)
    print(f"G1 coverage   {n} >= {MIN_SUBJECTS}  {'PASS' if res['gates']['G1_pass'] else 'FAIL'}")

    rng = np.random.default_rng(SEED)
    r_sh = spearman(aodd, aeven)
    sb = 2 * r_sh / (1 + r_sh) if np.isfinite(r_sh) and r_sh > -1 else float("nan")
    g2 = bool(np.isfinite(r_sh) and r_sh > 0.3)
    res["gates"]["G2"] = {"split_half_rho": r_sh, "spearman_brown_reliability": sb, "pass": g2}
    print(f"G2 halves     rho(odd, even) = {r_sh:+.4f}   Spearman-Brown reliability of the pooled "
          f"score = {sb:.4f}   {'PASS' if g2 else 'FAIL'}")

    pooled = spearman(g, apool)
    p_lo, p_hi = ci([spearman(g[i], apool[i])
                     for i in (rng.integers(0, n, n) for _ in range(REPS))])
    g3 = bool(np.isfinite(p_lo) and p_lo > 0)
    res["gates"]["G3"] = {"pooled": pooled, "lo": p_lo, "hi": p_hi, "pass": g3}
    print(f"G3 pooled     E86's D1 here: {pooled:+.4f} [{p_lo:+.4f}, {p_hi:+.4f}]  "
          f"{'PASS' if g3 else 'FAIL'}")
    if not (res["gates"]["G1_pass"] and g2 and g3):
        res["verdict"] = ("ABSENT -- a precondition failed (coverage, the halves not agreeing with each "
                          "other, or E86's pooled effect not present here), so nothing was tested "
                          "(rule 31).")
        print(f"\nVERDICT: {res['verdict']}")
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    # attenuation prediction: a half has reliability r_sh where the pooled score has sb, so an observed
    # correlation with the pooled score should shrink by sqrt(r_sh / sb) when measured against one half.
    shrink = float(np.sqrt(r_sh / sb)) if np.isfinite(sb) and sb > 0 else float("nan")
    predicted = pooled * shrink
    res["attenuation"] = {"shrink_factor": shrink, "predicted_half_rho": predicted}
    print(f"\nATTENUATION   a half has reliability {r_sh:.4f} against the pooled score's {sb:.4f}, so the "
          f"pooled {pooled:+.4f} predicts {predicted:+.4f} per half (shrink {shrink:.4f})")

    out = {}
    for nm, y in (("odd", aodd), ("even", aeven)):
        v = spearman(g, y)
        lo, hi = ci([spearman(g[i], y[i]) for i in (rng.integers(0, n, n) for _ in range(REPS))])
        out[nm] = {"rho": v, "lo": lo, "hi": hi,
                   "consistent_with_prediction": bool(np.isfinite(lo) and lo <= predicted <= hi)}
        print(f"P {nm:<5s}      {v:+.4f} [{lo:+.4f}, {hi:+.4f}]   "
              f"{'excludes 0' if np.isfinite(lo) and lo > 0 else 'includes 0'}   "
              f"prediction {predicted:+.4f} "
              f"{'inside' if out[nm]['consistent_with_prediction'] else 'OUTSIDE'} the interval")
    res["primary"] = out

    # G4 influence
    jack = np.array([spearman(np.delete(g, i), np.delete(apool, i)) for i in range(n)])
    worst = int(np.argmax(np.abs(jack - pooled)))
    res["gates"]["G4"] = {"max_abs_change": float(np.max(np.abs(jack - pooled))),
                          "subject": subs[worst], "min_rho": float(np.min(jack)),
                          "max_rho": float(np.max(jack))}
    print(f"G4 influence  leave-one-out pooled rho ranges [{jack.min():+.4f}, {jack.max():+.4f}]; "
          f"largest single deletion changes it by {np.max(np.abs(jack - pooled)):.4f} "
          f"(subject {subs[worst]})")

    pl_o, pl_e = [], []
    for _ in range(PLACEBO_DRAWS):
        perm = rng.permutation(n)          # SAME permutation for both halves: their agreement survives
        pl_o.append(spearman(g, aodd[perm]))
        pl_e.append(spearman(g, aeven[perm]))
    o_lo, o_hi = ci(pl_o)
    e_lo, e_hi = ci(pl_e)
    inside = {"odd": bool(o_lo <= out["odd"]["rho"] <= o_hi),
              "even": bool(e_lo <= out["even"]["rho"] <= e_hi)}
    res["placebo"] = {"odd": [o_lo, o_hi], "even": [e_lo, e_hi], "inside": inside}
    print(f"PLACEBO       odd [{o_lo:+.4f}, {o_hi:+.4f}] {'INSIDE' if inside['odd'] else 'outside'}   "
          f"even [{e_lo:+.4f}, {e_hi:+.4f}] {'INSIDE' if inside['even'] else 'outside'}")

    excl = {k: bool(np.isfinite(out[k]["lo"]) and out[k]["lo"] > 0 and not inside[k])
            for k in ("odd", "even")}
    cons = all(out[k]["consistent_with_prediction"] for k in ("odd", "even"))
    if not any(excl.values()):
        v = ("FAILS SPLIT-HALF -- the pooled association appears in NEITHER half of the very measurement "
             "it is about. Strong evidence that E86's D1 is noise in the pooled score, and E86 needs "
             "re-describing.")
    elif not all(excl.values()):
        which = [k for k, val in excl.items() if val]
        v = (f"INCONSISTENT -- the association survives in the {which} half only. Two halves of one "
             f"measurement should behave alike; one surviving and one not is what a marginal effect looks "
             f"like and is reported as INSTABILITY, not as partial support.")
    elif not cons:
        v = ("PASSES SIGN, FAILS SIZE -- both halves show the association but at magnitudes outside what "
             "pure attenuation predicts from the measured split-half reliability. Direction replicates, "
             "the quantitative model does not.")
    else:
        v = ("PASSES -- ge_norm predicts BOTH independent halves of BCI accuracy, in the same direction, "
             "at magnitudes consistent with the attenuation their reliability implies. E86 clears a test "
             "it could have failed. **This does NOT address the BH q = 0.0920 qualification**: the halves "
             "share subject, session, montage and day, so this is internal consistency and not an "
             "external replication. E108 remains the only route to that.")
    res["verdict"] = v
    print(f"\nVERDICT: {v}")
    json.dump(res, open(OUT, "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
