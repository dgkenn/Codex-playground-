"""E106 -- Is E86's `ge_norm` result just individual alpha frequency? The last standing qualification.

REGISTERED BEFORE ANY PARTIAL CORRELATION IS COMPUTED. No new data: `stieger_graph62.csv` joined to
`stieger_labels.csv`, the same 62 subjects E86 used.

=========================================================================================================
WHY THIS IS THE EXPERIMENT CHALLENGE B OWES
=========================================================================================================
E86 gave Challenge B its only primary to clear its gates: `ge_norm` D1 rho **+0.3069 [+0.0495, +0.5343]**
between subjects, outside its placebo, escape check against `deg` passing at +0.1837. Four qualifications
were filed with it. Three have been worked:

  * D2 (consecutive-session change) null -> E97 measured the ICC and called `ge_norm` trait-like, under
    which a null change score is expected by construction;
  * that trait reading's quantitative consequence -> E101;
  * BH q = 0.0920 across the family -> unchanged and still a qualification.

**The fourth was never touched and it is the sharpest: `iaf` also clears D1, at +0.2552 [+0.0185, +0.4685].**
Individual alpha frequency is one of the oldest and best-replicated BCI performance predictors there is
(the Blankertz 2010 line, named as E28's incumbent in this project's own ledger). If `ge_norm`'s
association is `iaf` wearing a graph-theoretic name, then Challenge B's one positive is a re-derivation of
a 2010 result and must be reported as that.

**This is rule 60 applied to the thing E86 did not check.** E86's escape gate tested `ge_norm` against
`deg` -- the connectivity family it was designed to escape -- and passed. It never tested it against the
SPECTRAL quantity that also predicts the outcome, because the escape check was aimed at the wrong family.

=========================================================================================================
PRIMARY -- symmetric, because "which one survives" is the whole question
=========================================================================================================
Subject means over all sessions, n = 62, exactly as E86 computed them.

    A   partial spearman( ge_norm , accuracy | iaf )
    B   partial spearman( iaf , accuracy | ge_norm )

Both are reported, always, and the verdict is a statement about the PAIR. Reporting only A would be the
selective import rule 59 was earned on. Partial rank correlation via residualising both variables on the
control's ranks, then correlating the residuals; subject bootstrap, 4000 reps, the residualisation refit
inside each replicate.

VERDICT, wrong direction FIRST (rule 37) -- and the "wrong" direction here is the one that helps us:

    (a) A's interval INCLUDES 0 and B's EXCLUDES 0 -> IT IS ALPHA FREQUENCY. `ge_norm`'s D1 does not
        survive adjustment for `iaf` while `iaf` survives adjustment for `ge_norm`. **Challenge B's one
        positive is a re-derivation of a known spectral predictor and must be described as that.** This is
        the outcome that costs the most and it is named first.
    (b) BOTH intervals include 0 -> MUTUALLY ABSORBED. The two measures share their association with
        accuracy and neither carries it alone at n = 62. Not support for `ge_norm`; the honest statement
        is that this deposit cannot separate them.
    (c) BOTH intervals exclude 0 -> INDEPENDENT CONTRIBUTIONS. Both predict accuracy after adjustment for
        the other, which would make `ge_norm` a genuine addition to the alpha-frequency predictor.
    (d) A's interval EXCLUDES 0 and B's INCLUDES 0 -> IT IS THE NETWORK MEASURE. `ge_norm` survives and
        `iaf` does not, which would strengthen E86 considerably.

PREDICTED: (b) MUTUALLY ABSORBED at ~45 %, (a) at ~30 %, (d) at ~15 %, (c) at ~10 %. Logged before the run.
The reason (b) leads: two predictors each at |rho| ~0.25-0.31 in 62 subjects have very little room to
separate, and rule 63's lesson is to say what the machinery can resolve before asking it to resolve
something.

=========================================================================================================
GATES
=========================================================================================================
    G0  RESOLVABILITY, computed and printed BEFORE the primary, because a null here means "cannot tell"
        rather than "no effect". The minimum detectable partial |rho| at n = 62 and 80 % power is about
        0.35; both raw associations are below that. **This gate cannot fail the experiment -- it fixes in
        advance how a null must be read**, which is rule 31's discipline applied at design time rather
        than after.
    G1  ESCAPE / COLLINEARITY (rule 60). |spearman(ge_norm, iaf)| must be < 0.90. If the two measures are
        the same measure, no partialling can separate them and the answer is that E86's primary and `iaf`
        are one variable. Reported as the finding, not as a gate failure.
    G2  COVERAGE. >= 50 subjects with all three of ge_norm, iaf and accuracy finite.
    G3  BOTH RAW ASSOCIATIONS PRESENT IN THIS RUN. `ge_norm` and `iaf` must each reproduce E86's raw D1
        with an interval excluding 0, recomputed here rather than quoted. If either does not, the premise
        is gone and the verdict is ABSENT (rule 31).

PLACEBO, and it gates: accuracy permuted across subjects, 500 draws, both partials recomputed. Any real
partial inside its own placebo's central 95 % is WITHDRAWN. The primary's interval is read FIRST -- a
placebo cannot validate or invalidate a null (rule 48).

SCOPE. Stieger BCI, motor-imagery control accuracy, 62 subjects. `ge_norm` is null-normalised global
efficiency of a wPLI alpha graph; `iaf` is individual alpha peak frequency. Nothing here concerns
consciousness, and BCI control accuracy is not a clinical outcome.
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
OUT = os.path.join(RESULTS, "e106_ge_norm_vs_iaf.json")

A_VAR, B_VAR = "ge_norm", "iaf"
ESCAPE_MAX = 0.90
MIN_SUBJECTS = 50
REPS = 4000
PLACEBO_DRAWS = 500
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


def partial_spearman(x, y, z):
    """Rank-partial correlation: residualise ranks of x and y on ranks of z, then correlate."""
    x, y, z = np.asarray(x, float), np.asarray(y, float), np.asarray(z, float)
    ok = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
    if ok.sum() < 8:
        return float("nan")
    rx, ry, rz = _rank(x[ok]), _rank(y[ok]), _rank(z[ok])
    if np.ptp(rz) <= 0:
        return spearman(rx, ry)
    A = np.column_stack([np.ones(rz.size), rz])
    bx, *_ = np.linalg.lstsq(A, rx, rcond=None)
    by, *_ = np.linalg.lstsq(A, ry, rcond=None)
    ex, ey = rx - A @ bx, ry - A @ by
    d = float(np.sqrt((ex ** 2).sum() * (ey ** 2).sum()))
    return float((ex * ey).sum() / d) if d > 1e-12 else float("nan")


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
    acc_by = {}
    for r in csv.DictReader(open(ACC, newline="")):
        if r.get("accuracy"):
            acc_by[(r["subject"], int(r["session"]))] = _f(r["accuracy"])
    by = defaultdict(list)
    for r in csv.DictReader(open(GRAPH, newline="")):
        k = (r["subject"], int(r["session"]))
        if k in acc_by:
            by[r["subject"]].append((r, acc_by[k]))

    subs = sorted(by)
    a = np.array([np.nanmean([_f(x[0].get(A_VAR, "")) for x in by[s]]) for s in subs])
    b = np.array([np.nanmean([_f(x[0].get(B_VAR, "")) for x in by[s]]) for s in subs])
    y = np.array([np.nanmean([x[1] for x in by[s]]) for s in subs])
    ok = np.isfinite(a) & np.isfinite(b) & np.isfinite(y)
    a, b, y = a[ok], b[ok], y[ok]
    n = int(a.size)
    res = {"n_subjects": n, "gates": {}}
    print(f"{len(subs)} subjects joined; {n} with {A_VAR}, {B_VAR} and accuracy all finite")

    # G0 RESOLVABILITY -- printed first, fixes how a null must be read
    mdr = 2.80 / np.sqrt(max(1, n - 3))       # ~80 % power, two-sided, Fisher-z approximation
    res["gates"]["G0_min_detectable_partial_rho"] = float(mdr)
    print(f"G0 resolvability  minimum detectable partial |rho| at n={n}, 80 % power ~ {mdr:.3f}")
    print(f"   -> a null below that magnitude means CANNOT TELL, not NO EFFECT. Fixed before the run.")

    esc = spearman(a, b)
    res["gates"]["G1_rho_ge_norm_iaf"] = esc
    res["gates"]["G1_pass"] = bool(np.isfinite(esc) and abs(esc) < ESCAPE_MAX)
    print(f"G1 escape         rho({A_VAR}, {B_VAR}) = {esc:+.4f}  "
          f"{'PASS' if res['gates']['G1_pass'] else 'FAIL'}")
    if not res["gates"]["G1_pass"]:
        res["verdict"] = (f"ONE VARIABLE -- {A_VAR} and {B_VAR} correlate at {esc:+.4f}; no partialling "
                          f"can separate them and E86's primary is {B_VAR} restated (rule 60).")
        print(f"\nVERDICT: {res['verdict']}")
        json.dump(res, open(OUT, "w"), indent=2)
        return 0

    res["gates"]["G2_pass"] = bool(n >= MIN_SUBJECTS)
    print(f"G2 coverage       {n} >= {MIN_SUBJECTS}  {'PASS' if res['gates']['G2_pass'] else 'FAIL'}")

    rng = np.random.default_rng(SEED)
    raw_a, raw_b = spearman(a, y), spearman(b, y)
    ra_lo, ra_hi = ci([spearman(a[i], y[i]) for i in (rng.integers(0, n, n) for _ in range(REPS))])
    rb_lo, rb_hi = ci([spearman(b[i], y[i]) for i in (rng.integers(0, n, n) for _ in range(REPS))])
    g3 = bool(not (ra_lo <= 0 <= ra_hi) and not (rb_lo <= 0 <= rb_hi))
    res["gates"].update({"G3_raw_a": [raw_a, ra_lo, ra_hi], "G3_raw_b": [raw_b, rb_lo, rb_hi],
                         "G3_pass": g3})
    print(f"G3 premise        raw {A_VAR:<8s} {raw_a:+.4f} [{ra_lo:+.4f}, {ra_hi:+.4f}]")
    print(f"                  raw {B_VAR:<8s} {raw_b:+.4f} [{rb_lo:+.4f}, {rb_hi:+.4f}]  "
          f"{'PASS' if g3 else 'FAIL'}")
    if not (res["gates"]["G2_pass"] and g3):
        res["verdict"] = ("ABSENT -- a precondition failed (coverage, or one of the two raw associations "
                          "this experiment exists to separate), so nothing was tested (rule 31).")
        print(f"\nVERDICT: {res['verdict']}")
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    pa = partial_spearman(a, y, b)
    pb = partial_spearman(b, y, a)
    ba, bb = [], []
    for _ in range(REPS):
        i = rng.integers(0, n, n)
        ba.append(partial_spearman(a[i], y[i], b[i]))
        bb.append(partial_spearman(b[i], y[i], a[i]))
    pa_lo, pa_hi = ci(ba)
    pb_lo, pb_hi = ci(bb)
    res["primary"] = {"A_ge_norm_given_iaf": {"rho": pa, "lo": pa_lo, "hi": pa_hi},
                      "B_iaf_given_ge_norm": {"rho": pb, "lo": pb_lo, "hi": pb_hi}}
    print(f"\nA  partial({A_VAR} , accuracy | {B_VAR})  {pa:+.4f} [{pa_lo:+.4f}, {pa_hi:+.4f}]")
    print(f"B  partial({B_VAR} , accuracy | {A_VAR})  {pb:+.4f} [{pb_lo:+.4f}, {pb_hi:+.4f}]")

    qa, qb = [], []
    for _ in range(PLACEBO_DRAWS):
        yp = y[rng.permutation(n)]
        qa.append(partial_spearman(a, yp, b))
        qb.append(partial_spearman(b, yp, a))
    qa_lo, qa_hi = ci(qa)
    qb_lo, qb_hi = ci(qb)
    a_inside = bool(qa_lo <= pa <= qa_hi)
    b_inside = bool(qb_lo <= pb <= qb_hi)
    res["placebo"] = {"A": [qa_lo, qa_hi, a_inside], "B": [qb_lo, qb_hi, b_inside]}
    print(f"PLACEBO accuracy permuted   A [{qa_lo:+.4f}, {qa_hi:+.4f}] "
          f"{'INSIDE' if a_inside else 'outside'}   B [{qb_lo:+.4f}, {qb_hi:+.4f}] "
          f"{'INSIDE' if b_inside else 'outside'}")

    a_ex = (not (pa_lo <= 0 <= pa_hi)) and not a_inside
    b_ex = (not (pb_lo <= 0 <= pb_hi)) and not b_inside
    tail = (f" NOTE G0: the minimum detectable partial |rho| here is ~{mdr:.3f}, so a null below that "
            f"magnitude is CANNOT TELL rather than NO EFFECT.")
    if (not a_ex) and b_ex:
        v = (f"IT IS ALPHA FREQUENCY -- {A_VAR} does not survive adjustment for {B_VAR} while {B_VAR} "
             f"survives adjustment for {A_VAR}. Challenge B's one positive is a re-derivation of a known "
             f"spectral predictor (the Blankertz 2010 line) and must be described as that.")
    elif (not a_ex) and (not b_ex):
        v = (f"MUTUALLY ABSORBED -- neither measure carries the association with accuracy after adjustment "
             f"for the other. This is NOT support for {A_VAR}; the honest statement is that 62 subjects "
             f"cannot separate them." + tail)
    elif a_ex and b_ex:
        v = (f"INDEPENDENT CONTRIBUTIONS -- both survive adjustment for the other, which makes {A_VAR} a "
             f"genuine addition to the alpha-frequency predictor rather than a restatement of it.")
    else:
        v = (f"IT IS THE NETWORK MEASURE -- {A_VAR} survives adjustment for {B_VAR} and {B_VAR} does not "
             f"survive adjustment for {A_VAR}. E86's primary is strengthened; the BH q = 0.0920 "
             f"qualification is untouched by this and still stands.")
    res["verdict"] = v
    print(f"\nVERDICT: {v}")
    json.dump(res, open(OUT, "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
