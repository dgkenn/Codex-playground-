"""E105 -- The candidate second axis is NOT perturbational. Does ongoing-EEG complexity escape the
aperiodic exponent AND its own family?

REGISTERED BEFORE THE v3 EXTRACTION LANDS, and before any correlation between `sham_evoked_lz` and the
complexity family has been computed. The rule-60 check below is a GATE, run first, not a footnote.

=========================================================================================================
WHERE THIS CAME FROM -- a control that outperformed the thing it was controlling for
=========================================================================================================
E104 delivered a clean null on the perturbational question: residual(real - sham | spont_exponent) gave
d_z **+0.1712 [-0.3894, +0.7598]** over 14 subjects, all five gates passing, with a perturbational response
demonstrably present (real-minus-sham evoked RMS +4.1139 [+0.0031, +9.8610]) and detection parity held.
The perturbation was delivered, was measurable, and bought nothing.

**But the SHAM arm -- built only as a control -- separated the states: d_z -0.7116 [-1.5936, -0.2066],
outside its own label-flip placebo [-0.6221, +0.5817].** Same recordings, same channels, same pipeline,
same residualisation on the exponent. So on this deposit something in the structure of ONGOING EEG carries
state information beyond the aperiodic slope, while the response to stimulation does not.

That is a candidate second axis and it is the first one this project has seen. It is also exactly the
situation rule 60 exists for.

=========================================================================================================
G1 IS THE RULE-60 GATE AND IT RUNS BEFORE ANYTHING ELSE
=========================================================================================================
`sham_evoked_lz` is the LZ76 complexity of a binarised map over (channels x 10 ms bins), each cell marking
whether that channel exceeded its OWN pre-epoch 95th percentile. It is a spatio-temporal variability
statistic. **It is not obviously different in kind from the amplitude-complexity family this project has
run into the ground**, and E73 is the precedent: a graph measure chosen precisely to escape the
connectivity family correlated with it at +0.9962 and the "network" test was a re-run of the connectivity
test.

So the v3 extraction adds `spont_lziv`, `spont_perm_entropy` and `spont_spectral_entropy`, computed on the
SAME inter-pulse intervals, the same channels and the same code path.

    G1  ESCAPE. |spearman(sham_evoked_lz, X)| < 0.90 across recordings for every X in
        {spont_lziv, spont_perm_entropy, spont_spectral_entropy, spont_exponent}.
        **If it fails, the answer is that the second axis is that family restated, and the experiment
        reports THAT** -- which is a real finding about what E104's sham arm was measuring, not a failure.
        The threshold is 0.90 because that is where E73's failure sat (+0.9962) and where rule 60 fixes it;
        it is a convention and is named as one (rule 63).

=========================================================================================================
PRIMARY
=========================================================================================================
Whichever spontaneous measures pass G1, the question is whether the state separation survives adjustment
for the WHOLE family rather than for the exponent alone. E104 removed one line; a family can hide behind
three.

    resid = sham_evoked_lz  with a multiple linear fit on [spont_exponent, spont_lziv,
                                spont_perm_entropy, spont_spectral_entropy] removed
    P   paired d_z of `resid`, awake minus sedated, within subject, 4000-rep subject bootstrap.

VERDICT, wrong direction FIRST (rule 37) -- and note the sign convention: E104's sham d_z was NEGATIVE,
i.e. SEDATED scored higher, so "the direction E104 saw" is negative here:

    (a) G1 FAILS -> NOT A NEW AXIS. `sham_evoked_lz` is the complexity family restated; E104's sham result
        is a fact about that family and the word "new" is withdrawn. Reported as the finding.
    (b) interval excludes 0 and POSITIVE -> REVERSED. The residual separates the states in the opposite
        direction to the raw measure, which is what adjustment-induced sign flips look like when the
        adjusters are collinear with the outcome. Not a second axis; read G3.
    (c) interval includes 0 -> ABSORBED BY THE FAMILY. The separation E104 saw is accounted for by
        spontaneous complexity measures already in this project's inventory. This is the outcome most
        consistent with everything else and it is not a disappointment: it would locate E104's sham result
        precisely.
    (d) interval excludes 0 and NEGATIVE -> A SECOND AXIS SURVIVES THE FAMILY. `sham_evoked_lz` carries
        state information that neither the aperiodic exponent nor three standard complexity measures
        carry. First such result in this project.

PREDICTED: (c), at roughly 55 %; (d) at roughly 25 %; (a) at roughly 20 %. Logged because the calibration
record is the point of logging predictions, and because (c) is the outcome that would NOT help.

=========================================================================================================
GATES
=========================================================================================================
    G1  ESCAPE, above. Runs first.
    G2  COVERAGE. >= 12 subjects with both conditions, matching E104.
    G3  ADJUSTER COLLINEARITY. The condition number of the design matrix must be finite and the adjusters
        must each vary; a multiple fit on collinear regressors produces unstable residuals and a sign flip
        is then an artefact of the fit rather than a result. Reported, and it gates branch (b).
    G4  POSITIVE CONTROL, unchanged from E104: `spont_exponent` must separate the states against a
        Gaussian on the same pairs. It did, at d_z -0.8424 vs 0.5982 -- but it is recomputed here from
        this run's own table and not quoted.
    G5  THE RAW EFFECT MUST BE PRESENT IN THIS TABLE. `sham_evoked_lz` unadjusted must reproduce E104's
        separation. If v3's extraction changed it, the premise of this experiment is gone and the verdict
        is ABSENT, not a null (rule 31).

PLACEBO, gating the verdict: awake/sed labels flipped at random within subject, 500 draws, the whole fit
and residualisation recomputed inside each. **The primary's interval is read FIRST** -- a placebo cannot
validate or invalidate a null (rule 48), and if the primary contains zero the placebo is reported as not
informative rather than as a withdrawal.

EXCLUSIONS: sub-1016 and sub-1074, unchanged from E103/E104 and for the same burn-in reason (rule 26).

SCOPE: ds005620, light sedation, 14 subjects, 64 channels. `sham_evoked_lz` is a spatio-temporal
variability statistic on a fixed per-channel threshold. A positive result would be a statement about state
separation on this deposit and NOT about consciousness: no experiential report, responsiveness assessment
or behavioural measure exists here.
"""
from __future__ import annotations

import csv
import json
import os
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
TABLE = os.path.join(RESULTS, "ds005620_perturbation_v3.csv")
OUT = os.path.join(RESULTS, "e105_ongoing_complexity_second_axis.json")

TARGET = "sham_evoked_lz"
FAMILY = ["spont_exponent", "spont_lziv", "spont_perm_entropy", "spont_spectral_entropy"]
ESCAPE_MAX = 0.90
EXCLUDE_SUBJECTS = {"1016", "1074"}
MIN_SUBJECTS = 12
REPS = 4000
PLACEBO_DRAWS = 500
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def dz(d):
    d = np.asarray([x for x in d if np.isfinite(x)], float)
    if d.size < 3 or d.std(ddof=1) <= 0:
        return float("nan")
    return float(d.mean() / d.std(ddof=1))


def ci(v):
    v = np.sort(np.asarray([x for x in v if np.isfinite(x)], float))
    if v.size < 50:
        return float("nan"), float("nan")
    return float(np.quantile(v, .025)), float(np.quantile(v, .975))


def spearman(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 5 or np.ptp(x[ok]) <= 0 or np.ptp(y[ok]) <= 0:
        return float("nan")
    rx = np.argsort(np.argsort(x[ok])).astype(float)
    ry = np.argsort(np.argsort(y[ok])).astype(float)
    rx -= rx.mean(); ry -= ry.mean()
    d = float(np.sqrt((rx ** 2).sum() * (ry ** 2).sum()))
    return float((rx * ry).sum() / d) if d > 1e-12 else float("nan")


def multi_resid(y, X):
    """y with a multiple least-squares fit on the columns of X removed (intercept included)."""
    ok = np.isfinite(y) & np.all(np.isfinite(X), axis=1)
    out = np.full_like(y, np.nan, dtype=float)
    if ok.sum() < X.shape[1] + 3:
        return out, float("inf")
    A = np.column_stack([np.ones(ok.sum()), X[ok]])
    cond = float(np.linalg.cond(A))
    beta, *_ = np.linalg.lstsq(A, y[ok], rcond=None)
    out[ok] = y[ok] - A @ beta
    return out, cond


def paired(both, values, labels, subj):
    out = []
    for s, idxs in both.items():
        a = [values[i] for i in idxs if labels[i] == "awake" and np.isfinite(values[i])]
        b = [values[i] for i in idxs if labels[i] == "sed" and np.isfinite(values[i])]
        if a and b:
            out.append(float(np.mean(a) - np.mean(b)))
    return np.array(out, float)


def main() -> int:
    if not os.path.exists(TABLE):
        print(f"ABSENT: {TABLE} -- v3 extraction has not landed")
        return 2
    rows = [r for r in csv.DictReader(open(TABLE, newline=""))
            if r.get("status") == "ok" and r.get("subject") not in EXCLUDE_SUBJECTS
            and r.get("task") in ("awake", "sed")]
    res = {"n_rows": len(rows), "gates": {}}
    col = lambda k: np.array([_f(r.get(k, "")) for r in rows], float)      # noqa: E731
    subj = [r["subject"] for r in rows]
    task = [r["task"] for r in rows]
    by = defaultdict(list)
    for i, s in enumerate(subj):
        by[s].append(i)
    both = {s: ix for s, ix in by.items()
            if any(task[i] == "awake" for i in ix) and any(task[i] == "sed" for i in ix)}
    print(f"{len(rows)} ok recordings, {len(both)} subjects with both conditions")

    y = col(TARGET)
    X = np.column_stack([col(f) for f in FAMILY])
    rng = np.random.default_rng(SEED)

    # ---- G1 ESCAPE, first ------------------------------------------------------------------------
    print(f"\nG1 ESCAPE (rule 60) -- {TARGET} against the family it must differ from:")
    esc, g1 = {}, True
    for j, f in enumerate(FAMILY):
        r = spearman(y, X[:, j])
        esc[f] = r
        bad = bool(np.isfinite(r) and abs(r) >= ESCAPE_MAX)
        g1 = g1 and not bad
        print(f"   rho({TARGET}, {f:<24s}) = {r:+.4f}   {'FAILS' if bad else 'ok'}")
    res["gates"]["G1_escape"] = esc
    res["gates"]["G1_pass"] = g1
    print(f"G1 {'PASS' if g1 else 'FAIL'} (threshold |rho| < {ESCAPE_MAX})")
    if not g1:
        worst = max(esc, key=lambda k: abs(esc[k]) if np.isfinite(esc[k]) else -1)
        res["verdict"] = (f"NOT A NEW AXIS -- {TARGET} correlates with {worst} at {esc[worst]:+.4f}, so "
                          f"E104's sham result is a fact about that measure restated. The word 'new' is "
                          f"withdrawn; this is the finding, not a failure (rule 60).")
        print(f"\nVERDICT: {res['verdict']}")
        json.dump(res, open(OUT, "w"), indent=2)
        return 0

    # ---- G2 coverage, G4 known effect, G5 the premise ---------------------------------------------
    res["gates"]["G2_subjects"] = len(both)
    res["gates"]["G2_pass"] = bool(len(both) >= MIN_SUBJECTS)
    d_sp = paired(both, col("spont_exponent"), task, subj)
    sp_dz = dz(d_sp)
    noise95 = float(np.quantile(np.abs([dz(rng.normal(size=max(3, d_sp.size))) for _ in range(2000)]), .95))
    res["gates"].update({"G4_spont_dz": sp_dz, "G4_noise_95": noise95,
                         "G4_pass": bool(np.isfinite(sp_dz) and abs(sp_dz) > noise95)})
    d_raw = paired(both, y, task, subj)
    raw_dz = dz(d_raw)
    raw_lo, raw_hi = ci([dz(d_raw[rng.integers(0, d_raw.size, d_raw.size)]) for _ in range(REPS)])
    res["gates"].update({"G5_raw_dz": raw_dz, "G5_lo": raw_lo, "G5_hi": raw_hi,
                         "G5_pass": bool(np.isfinite(raw_lo) and not (raw_lo <= 0.0 <= raw_hi))})
    print(f"G2 coverage  {len(both)} subjects  {'PASS' if res['gates']['G2_pass'] else 'FAIL'}")
    print(f"G4 known     spont_exponent d_z {sp_dz:+.4f} vs Gaussian 95th {noise95:.4f}  "
          f"{'PASS' if res['gates']['G4_pass'] else 'FAIL'}")
    print(f"G5 premise   raw {TARGET} d_z {raw_dz:+.4f} [{raw_lo:+.4f}, {raw_hi:+.4f}]  "
          f"{'PASS' if res['gates']['G5_pass'] else 'FAIL'}")

    resid, cond = multi_resid(y, X)
    res["gates"]["G3_condition_number"] = cond
    res["gates"]["G3_pass"] = bool(np.isfinite(cond) and cond < 1e6)
    print(f"G3 adjusters condition number {cond:.1f}  "
          f"{'PASS' if res['gates']['G3_pass'] else 'FAIL'}")

    if not (res["gates"]["G2_pass"] and res["gates"]["G4_pass"] and res["gates"]["G5_pass"]
            and res["gates"]["G3_pass"]):
        res["verdict"] = ("ABSENT -- a precondition failed (coverage, known effect, adjuster stability, or "
                          "the raw effect this experiment exists to explain), so nothing was tested "
                          "(rule 31).")
        print(f"\nVERDICT: {res['verdict']}")
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    # ---- PRIMARY ----------------------------------------------------------------------------------
    d = paired(both, resid, task, subj)
    point = dz(d)
    lo, hi = ci([dz(d[rng.integers(0, d.size, d.size)]) for _ in range(REPS)])
    res["primary"] = {"d_z": point, "lo": lo, "hi": hi, "n_subjects": int(d.size)}
    print(f"\nP  residual({TARGET} | whole family) awake-minus-sed  d_z {point:+.4f} "
          f"[{lo:+.4f}, {hi:+.4f}]  over {d.size} subjects")

    pl = []
    for _ in range(PLACEBO_DRAWS):
        flip = {s: bool(rng.integers(0, 2)) for s in both}
        lab = [("sed" if flip.get(subj[i], False) and task[i] == "awake" else
                "awake" if flip.get(subj[i], False) and task[i] == "sed" else task[i])
               for i in range(len(rows))]
        v = dz(paired(both, resid, lab, subj))
        if np.isfinite(v):
            pl.append(v)
    p_lo, p_hi = ci(pl)
    inside = bool(np.isfinite(p_lo) and p_lo <= point <= p_hi)
    res["placebo"] = {"lo": p_lo, "hi": p_hi, "inside": inside, "n_draws": len(pl)}
    print(f"PLACEBO label flip: [{p_lo:+.4f}, {p_hi:+.4f}]  real {'INSIDE' if inside else 'outside'}")

    excl = not (lo <= 0.0 <= hi)
    if not excl:
        v = ("ABSORBED BY THE FAMILY -- the state separation E104's sham arm showed is accounted for by "
             "spontaneous complexity measures already in this project's inventory. The placebo is NOT "
             "informative here: there was no effect for it to fail to reproduce (rule 48).")
    elif inside:
        v = ("WITHDRAWN BY PLACEBO -- a random label flip reproduces the residual separation.")
    elif point > 0:
        v = ("REVERSED -- the residual separates in the opposite direction to the raw measure, which is "
             f"what collinear adjustment produces; condition number {cond:.1f}. Not a second axis.")
    else:
        v = ("A SECOND AXIS SURVIVES THE FAMILY -- sham_evoked_lz carries state information that neither "
             "the aperiodic exponent nor three standard complexity measures carry. First such result in "
             "this project. Scope travels with it permanently: 14 subjects, light sedation, and no "
             "experiential measure exists in this deposit.")
    res["verdict"] = v
    print(f"\nVERDICT: {v}")
    json.dump(res, open(OUT, "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
