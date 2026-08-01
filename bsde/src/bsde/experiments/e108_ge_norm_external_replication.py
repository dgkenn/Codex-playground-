"""E108 -- EXTERNAL REPLICATION of E86: does `ge_norm` predict BCI performance in a second cohort?

REGISTERED BEFORE THE PREDICTOR TABLE IS COMPLETE and before any correlation with accuracy has been
computed. `eegmmidb_bci.csv` (the outcome) has existed since long before this design and no network measure
has ever been near it.

=========================================================================================================
WHY THIS IS THE ONLY EXPERIMENT THAT CAN CLOSE E86's LAST QUALIFICATION
=========================================================================================================
E86 is Challenge B's only positive: `ge_norm` predicts BCI accuracy between subjects at D1 rho +0.3069
[+0.0495, +0.5343]. Three of its four qualifications have been worked -- E97 (trait-like, so the null D2 is
expected by construction), E101 (that trait model is not separable from noise at n = 61: d_error +0.0161
[-0.0456, +0.0710], d_noise -0.0969 [-0.2096, +0.0173]), E106 (it is NOT alpha frequency: rho(ge_norm, iaf)
= +0.0781, partials +0.2837 and +0.2423).

**All three are the same 62 Stieger subjects, and the surviving qualification is multiplicity: BH q =
0.0920 across the E86 family.** No further analysis of that cohort can fix it. A correction exists because
several measures were examined; **a single pre-registered hypothesis tested once in an independent cohort
has a family of size one and needs no correction at all.** That is what this is.

=========================================================================================================
THE ONE HYPOTHESIS, FIXED HERE
=========================================================================================================
    P   spearman( ge_norm , imagery_auc ) across eegmmidb subjects, PREDICTED POSITIVE.

    `ge_norm` per subject = the MEAN of the two resting runs (R01 eyes-open, R02 eyes-closed). **Declared
    here, before the data is read, precisely so that the better-performing run cannot be chosen later.**
    Single-run values are reported as secondary and are not the test.

    Case bootstrap over subjects, 4000 reps.

VERDICT, wrong direction FIRST (rule 37):

    (a) interval excludes 0 and NEGATIVE -> CONTRADICTED. The association runs the other way in an
        independent cohort, which is worse for E86 than a null.
    (b) interval includes 0 -> NOT REPLICATED -- and the report must then say WHICH KIND of failure it is,
        because the two are not the same claim (rule 31). If E86's point estimate +0.3069 lies INSIDE this
        interval, the replication is UNDERPOWERED and compatible with E86; if +0.3069 lies OUTSIDE, the
        replication actively excludes an effect of E86's size. Both are computed and printed.
    (c) interval excludes 0 and POSITIVE -> REPLICATED. E86's multiplicity qualification is answered, not
        by correction, but by an independent test with a family of size one.

PREDICTED: (c) at ~35 %, (b)-underpowered at ~40 %, (b)-excluding at ~20 %, (a) at ~5 %. The reason (c) is
below even money despite E86 being real in its own cohort is written in the next section.

=========================================================================================================
WHAT NECESSARILY DIFFERS, WRITTEN BEFORE THE RESULT SO IT CANNOT BECOME AN EXCUSE AFTERWARDS
=========================================================================================================
A failure here has several available explanations and this list is fixed in advance so that none of them
can be selected after seeing the number:

  1. **The outcome is a different construct.** Stieger's accuracy is ONLINE BCI CONTROL over real sessions.
     `imagery_auc` is CROSS-VALIDATED DECODABILITY of left-versus-right imagery from the same subject's
     trials. Decodability is an upper bound on control; a subject can be decodable and still control badly.
  2. **The resting state is different.** Stieger's predictor came from the PRE-CUE period of task trials;
     this comes from dedicated baseline runs, one eyes-open and one eyes-closed.
  3. **Montage and sampling differ** -- 64 channels at 160 Hz against 62 at 1000 Hz. `ge_norm` is
     null-normalised, which is what makes it comparable across graph sizes at all and is why E86's primary
     was this rather than raw `ge`.
  4. **One session per subject**, so E97's trait-averaging advantage is unavailable: E101 measured that a
     single-session `ge_norm` is attenuated relative to a 3-session mean by a factor of about 1.27.
     **A replication estimate around +0.24 rather than +0.31 is therefore what a TRUE effect of E86's size
     predicts here**, and that arithmetic is stated now rather than after.

=========================================================================================================
GATES
=========================================================================================================
    G1  COVERAGE. >= 80 subjects with `ge_norm` on at least one rest run and a finite `imagery_auc`.
    G2  THE OUTCOME MUST BE ALIVE (the E33/E61 rule). `imagery_auc` must vary across subjects AND the
        cohort must contain real decoding: the median must exceed 0.5 and a reasonable fraction of
        subjects must beat their own permutation null, using the `perm_p` column already in the table.
        **If nobody can be decoded, there is no performance for anything to predict** and the verdict is
        ABSENT, not a null.
    G3  PREDICTOR SANITY. `ge_norm` must vary across subjects and lie in a plausible range; a
        null-normalised efficiency should sit near 1. Reported with its spread.
    G4  ESCAPE, carried over from E106: rho(ge_norm, iaf) on THIS cohort, plus `iaf`'s own association with
        the outcome. If `iaf` replicates and `ge_norm` does not, that is a different and important
        finding, so both are always reported (rule 59 -- import the whole row, never a selected part).

PLACEBO, gating the verdict: `imagery_auc` permuted across subjects, 2000 draws. Real estimate inside the
placebo's central 95 % is WITHDRAWN. The primary's interval is read FIRST (rule 48).

SCOPE. eegmmidb, motor-imagery decodability, resting-state graph measures. Nothing here concerns
consciousness or any clinical outcome.
"""
from __future__ import annotations

import csv
import json
import os
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
GRAPH = os.path.join(RESULTS, "eegmmidb_graph.csv")
BCI = os.path.join(RESULTS, "eegmmidb_bci.csv")
OUT = os.path.join(RESULTS, "e108_ge_norm_external_replication.json")

PRIMARY = "ge_norm"
OUTCOME = "imagery_auc"
E86_POINT = 0.3069
E101_ATTENUATION = 1.267          # 3-session mean vs single session, measured in E101
MIN_SUBJECTS = 80
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


def boot(x, y, rng, reps=REPS):
    n = x.size
    return ci([spearman(x[i], y[i]) for i in (rng.integers(0, n, n) for _ in range(reps))])


def main() -> int:
    for p in (GRAPH, BCI):
        if not os.path.exists(p):
            print(f"ABSENT: {p}")
            return 2
    runs = defaultdict(dict)
    for r in csv.DictReader(open(GRAPH, newline="")):
        if r.get("status") == "ok":
            runs[r["subject"]][r["run"]] = r
    out = {}
    for r in csv.DictReader(open(BCI, newline="")):
        if r.get("status") == "ok" and r.get(OUTCOME):
            out[r["subject"]] = r

    subs = sorted(set(runs) & set(out))
    def gmean(s, key):
        vals = [_f(v.get(key, "")) for v in runs[s].values()]
        vals = [v for v in vals if np.isfinite(v)]
        return float(np.mean(vals)) if vals else float("nan")

    x = np.array([gmean(s, PRIMARY) for s in subs])
    y = np.array([_f(out[s][OUTCOME]) for s in subs])
    iaf = np.array([gmean(s, "iaf") for s in subs])
    pp = np.array([_f(out[s].get("perm_p", "")) for s in subs])
    ok = np.isfinite(x) & np.isfinite(y)
    x, y, iaf, pp = x[ok], y[ok], iaf[ok], pp[ok]
    subs = [s for s, k in zip(subs, ok) if k]
    n = x.size

    res = {"n_subjects": n, "gates": {}}
    print(f"{len(runs)} subjects with graph rows, {len(out)} with an outcome; {n} usable")
    res["gates"]["G1_pass"] = bool(n >= MIN_SUBJECTS)
    print(f"G1 coverage   {n} >= {MIN_SUBJECTS}  {'PASS' if res['gates']['G1_pass'] else 'FAIL'}")

    med_auc = float(np.median(y))
    frac_sig = float(np.mean(pp < 0.05)) if np.isfinite(pp).any() else float("nan")
    g2 = bool(np.ptp(y) > 0 and med_auc > 0.5 and np.isfinite(frac_sig) and frac_sig >= 0.20)
    res["gates"].update({"G2_median_auc": med_auc, "G2_frac_perm_p_lt_05": frac_sig,
                         "G2_auc_spread": float(np.ptp(y)), "G2_pass": g2})
    print(f"G2 outcome    median {OUTCOME} {med_auc:.4f}, spread {np.ptp(y):.4f}, "
          f"{frac_sig*100:.1f} % of subjects beat their own permutation null  "
          f"{'PASS' if g2 else 'FAIL'}")

    g3 = bool(np.ptp(x) > 0)
    res["gates"].update({"G3_ge_norm_median": float(np.median(x)),
                         "G3_ge_norm_sd": float(np.std(x)), "G3_pass": g3})
    print(f"G3 predictor  {PRIMARY} median {np.median(x):.4f}, sd {np.std(x):.4f}, "
          f"range [{x.min():.4f}, {x.max():.4f}]  {'PASS' if g3 else 'FAIL'}")

    if not (res["gates"]["G1_pass"] and g2 and g3):
        res["verdict"] = ("ABSENT -- a precondition failed. If G2 failed there is no decodable "
                          "performance for anything to predict, and that is not a null about ge_norm "
                          "(rule 31).")
        print(f"\nVERDICT: {res['verdict']}")
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    rng = np.random.default_rng(SEED)
    point = spearman(x, y)
    lo, hi = boot(x, y, rng)
    res["primary"] = {"rho": point, "lo": lo, "hi": hi, "n": n}
    print(f"\nP  spearman({PRIMARY}, {OUTCOME}) = {point:+.4f} [{lo:+.4f}, {hi:+.4f}]  over {n} subjects")
    expected = E86_POINT / E101_ATTENUATION
    print(f"   E86 was {E86_POINT:+.4f} on 3-session means; a TRUE effect of that size predicts about "
          f"{expected:+.4f} here (E101's single-session attenuation {E101_ATTENUATION:.3f})")

    # G4 escape and the comparator -- both always reported (rule 59)
    esc = spearman(x, iaf)
    i_point = spearman(iaf, y)
    i_lo, i_hi = boot(iaf, y, rng)
    res["gates"]["G4"] = {"rho_ge_norm_iaf": esc, "iaf_vs_outcome": [i_point, i_lo, i_hi]}
    print(f"G4 escape     rho({PRIMARY}, iaf) = {esc:+.4f}   "
          f"iaf vs {OUTCOME}: {i_point:+.4f} [{i_lo:+.4f}, {i_hi:+.4f}]")

    pl = [spearman(x, y[rng.permutation(n)]) for _ in range(PLACEBO_DRAWS)]
    p_lo, p_hi = ci(pl)
    inside = bool(np.isfinite(p_lo) and p_lo <= point <= p_hi)
    res["placebo"] = {"lo": p_lo, "hi": p_hi, "inside": inside}
    print(f"PLACEBO outcome permuted: [{p_lo:+.4f}, {p_hi:+.4f}]  "
          f"real {'INSIDE' if inside else 'outside'}")

    excl = not (lo <= 0.0 <= hi)
    e86_inside = bool(lo <= E86_POINT <= hi)
    exp_inside = bool(lo <= expected <= hi)
    res["compatibility"] = {"E86_point_inside_CI": e86_inside, "attenuated_expectation": expected,
                            "attenuated_inside_CI": exp_inside}
    if excl and point < 0:
        v = ("CONTRADICTED -- the association runs the OTHER WAY in an independent cohort, which is worse "
             "for E86 than a null and cannot be explained by any of the four pre-listed differences.")
    elif not excl:
        kind = ("UNDERPOWERED and COMPATIBLE with E86" if (e86_inside or exp_inside) else
                "and it EXCLUDES an effect of E86's size")
        v = (f"NOT REPLICATED, {kind}. The interval [{lo:+.4f}, {hi:+.4f}] "
             f"{'contains' if (e86_inside or exp_inside) else 'does not contain'} E86's {E86_POINT:+.4f} "
             f"or its attenuated expectation {expected:+.4f}. E86's multiplicity qualification "
             f"(BH q = 0.0920) therefore STANDS. The placebo is not informative here (rule 48).")
    elif inside:
        v = "WITHDRAWN BY PLACEBO -- permuting the outcome reproduces the estimate."
    else:
        v = ("REPLICATED -- ge_norm predicts BCI performance in an independent cohort, tested once, with a "
             "family of size one. E86's surviving multiplicity qualification is answered by independence "
             "rather than by correction. The four pre-listed differences (online control vs decodability, "
             "task-baseline vs dedicated rest, montage, single session) make this a CONCEPTUAL rather than "
             "an exact replication and it must be described as one.")
    res["verdict"] = v
    print(f"\nVERDICT: {v}")
    json.dump(res, open(OUT, "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
