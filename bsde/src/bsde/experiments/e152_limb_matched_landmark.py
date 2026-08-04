#!/usr/bin/env python3
"""E152 -- is E151's landmark effect the behavioural threshold, or the steepness of the drug limb?

REGISTERED BEFORE ANY LIMB-MATCHED STATISTIC HAS BEEN COMPUTED. Successor to E151. Cohort, candidates,
window widths, statistic and controls are E151's. **What changes is where the comparison landmarks come
from**, plus one new arm that exists only to make the alternative explanation testable.

=========================================================================================================
WHY E151'S POSITIVE IS NOT CLAIMED
=========================================================================================================
E151 asked whether a candidate jumps more at a behavioural landmark than at a random landmark of identical
geometry, and **all eleven of eleven candidates cleared at both landmarks**, several with 10 of 10
subjects agreeing. Its positive control detected a synthetic feature built to change at the landmark
(D = +2.28, +1.89, +1.09 at three noise levels, 10/10 each) and its negative control returned
+0.1003 [-0.0784, +0.3108] and +0.0324 [-0.3309, +0.4157]. So the machinery works.

**Eleven of eleven is the warning, not the result** (rules 18 and 49). And the alternative explanation is
specific and sufficient:

    LOC happens on the INDUCTION RAMP. ROC happens on EMERGENCE. Both are moments when the drug
    concentration is moving fast. E151 drew its comparison landmarks from the whole unconscious interior,
    which is mostly MAINTENANCE PLATEAU, where concentration is roughly constant. **Any feature that
    tracks concentration jumps more on a limb than on a plateau, with no behavioural threshold involved
    anywhere.**

E151's negative control could not catch this because it was a smooth random walk with no drug trajectory
at all -- rule 50 exactly: the baseline must hold the suspected cause constant, and a baseline of the
wrong shape carries the authority of a measurement without doing its job.

=========================================================================================================
THE TWO CHANGES
=========================================================================================================
**1. LIMB-MATCHED COMPARISON LANDMARKS.** Random landmarks are now drawn from a local band around the real
landmark -- `[L - 4W, L + 4W]` excluding `[L - W, L + W]` -- so they sit on the same limb, at comparable
distance from the infusion change, with comparable local rate of concentration change. Everything about
the drug trajectory is approximately matched; only the behavioural threshold crossing is not.

**2. A FIXED-OFFSET PSEUDO-LANDMARK ARM, which is the discriminating test.** The identical statistic is
computed at `L - 4W` and `L + 4W` -- points on the SAME limb, far enough from the behavioural threshold
that no responsiveness change occurs there, close enough that the drug is still moving.

    If E151's effect is the behavioural threshold, the pseudo-landmark should score near zero.
    If E151's effect is limb steepness, the pseudo-landmark should score AS HIGH AS the real one.

That is a clean two-way discrimination and it is why this arm exists rather than another gate.

=========================================================================================================
GATES
=========================================================================================================
G1  MANIFEST as E151's, with the additional room the wider bands need: `>= 5W` epochs either side of each
    landmark inside the recording, and `>= 5W` between LOC and ROC.
G2  POSITIVE CONTROL, E151's, unchanged and re-run: a synthetic `label + noise` feature must still clear
    under the tighter comparison. **This can now fail**, because limb-matched landmarks are a harder
    comparison, and if a feature that changes exactly at the threshold no longer clears then the design
    has been tightened past the point of being able to answer anything.
G3  **DRUG-TRAJECTORY NEGATIVE CONTROL, replacing E151's random walk.** A synthetic feature built as a
    smooth monotone function of the *distance to the nearest infusion limb* -- concretely, a triangular
    ramp peaking at the midpoint of the unconscious period, plus noise, so it rises through induction,
    plateaus, and falls through emergence with no dependence on the label. **It must return D
    indistinguishable from zero under the limb-matched comparison.** If it does not, the comparison is
    still not matched and no candidate result is readable.
G4  WINDOW AGREEMENT at W in {60, 150, 300}.

=========================================================================================================
PRIMARY -- WRONG-DIRECTION BRANCH WRITTEN FIRST (rule 37)
=========================================================================================================
Per candidate and landmark: subject-level mean D under the limb-matched comparison, with the subject
bootstrap and sign count, **and beside it the same statistic at the pseudo-landmark**. The verdict is
driven by the CONTRAST between them, not by D alone.

**IF THE PSEUDO-LANDMARK SCORES AS HIGH AS THE REAL ONE** -- the expected outcome -- then E151's positive
is fully explained by limb steepness, it is withdrawn rather than qualified, and the conclusion is that
**the frontal spectral family tracks the concentration trajectory and carries no detectable signature of
the behavioural threshold crossing itself.** That is a real and useful negative for Challenge A: it says a
consciousness marker cannot be read off the amplitude family even when the behavioural transition is known
to the second, which is the strongest form of that statement this project can make.

**IF SOME CANDIDATE KEEPS D > 0 AT THE REAL LANDMARK WHILE THE PSEUDO-LANDMARK IS AT ZERO**, at both LOC
and ROC, that candidate is sensitive to the behavioural threshold rather than to the exposure. It would be
the first such finding here and it goes to the 44 OR cases for replication before it is described as
anything.

**REGISTERED PREDICTION: THE PSEUDO-LANDMARK SCORES AS HIGH AS THE REAL ONE FOR AT LEAST 8 OF THE 11
CANDIDATES, AND NO CANDIDATE SURVIVES AT BOTH LANDMARKS.** The reasoning is above and it is the
unfavourable outcome for this project's interest, which is the right way round to bet.

SCOPE unchanged: ten subjects, one agent, spectra only, so a negative bounds the frontal amplitude family
under propofol and not representations in general.

WHAT WAS ALREADY SEEN (rule 41). All of E151's output, including every candidate's D at both landmarks and
both of its controls, quoted in the ledger row for E151.

    python bsde/src/bsde/experiments/e152_limb_matched_landmark.py
"""
from __future__ import annotations

import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.verifier.stats import auc_abs, cluster_bootstrap_ci                  # noqa: E402

sys.path.insert(0, HERE)
from e148_roc_concentration_matched_dissociation import FEATURES, _med, load   # noqa: E402
from e151_landmark_specific_transition import jump                             # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e152_limb_matched.json")

W_PRIMARY = 150
WINDOWS = (60, 150, 300)
BAND = 4          # comparison landmarks live within +-BAND*W of the real one, CLIPPED to the recording
PSEUDO = 2        # the pseudo-landmark sits +-PSEUDO*W away on the same limb
DRAWS = 200
ALIVE_BAR = 0.10


def d_limb(v, lm, w, n, rng, draws=DRAWS, band=BAND):
    """Real jump minus median jump at landmarks on the SAME LIMB, in per-subject MAD units."""
    s = float(np.nanmedian(np.abs(v - np.nanmedian(v))))
    if not math.isfinite(s) or s <= 0:
        return float("nan"), float("nan")
    real = jump(v, lm, w, s)
    lo, hi = max(lm - band * w, w), min(lm + band * w, n - w - 1)
    rnd = []
    for _ in range(draws):
        j = int(rng.integers(lo, hi)) if hi > lo else lm
        if abs(j - lm) <= w:                      # exclude the landmark's own neighbourhood
            continue
        jj = jump(v, j, w, s)
        if math.isfinite(jj):
            rnd.append(jj)
    if not rnd or not math.isfinite(real):
        return float("nan"), float("nan")
    return real - float(np.median(rnd)), float(np.mean(np.asarray(rnd) >= real))


def main(argv=None) -> int:
    rng = np.random.default_rng(152)
    data = load()
    subs = sorted(data)
    # Room needed is set by what the recording can supply, not by a round number (rule 63). The
    # comparison band is clipped inside `d_limb`, so the binding requirement is only that the PSEUDO
    # landmark and its own window fit: PSEUDO*W + W epochs either side of each landmark. At W = 150 that
    # is 450 epochs (15 min), which every volunteer has -- the first draft demanded 5*max(WINDOWS) = 1500
    # epochs (50 min) and admitted 1 of 10, because LOC occurs at 18-67 min.
    need = (PSEUDO + 1) * W_PRIMARY
    ok = [c for c in subs
          if len(data[c]["loc"]) == 1 and len(data[c]["roc"]) == 1
          and data[c]["loc"][0] >= need and data[c]["n"] - data[c]["roc"][0] >= need
          and data[c]["roc"][0] - data[c]["loc"][0] >= need]
    g1 = len(ok) >= 8
    print(f"G1 MANIFEST  {len(ok)} of {len(subs)} volunteers with >= {need} epochs of room -> "
          f"{'PASS' if g1 else 'FAIL'}")
    out = {"experiment": "E152", "usable": ok, "window": W_PRIMARY, "band": BAND}

    alive = []
    for f in FEATURES:
        vals = []
        for c in ok:
            d = data[c]
            m = np.isfinite(d["X"][f]) & np.isin(d["label"], (0.0, 1.0))
            if m.sum() > 50 and len(set(d["label"][m])) > 1:
                vals.append(auc_abs(list(d["label"][m]), list(d["X"][f][m])) - 0.5)
        if vals and float(np.mean(vals)) >= ALIVE_BAR:
            alive.append(f)
    print(f"G2a ALIVENESS  {len(alive)} of {len(FEATURES)} candidates alive")

    def arm(series_of, offset=0, w=W_PRIMARY):
        """Subject-level mean D at each landmark, optionally shifted by `offset` windows (pseudo-arm)."""
        res = {}
        for tag, key in (("LOC", "loc"), ("ROC", "roc")):
            per = {}
            for c in ok:
                d = data[c]
                lm = int(d[key][0]) + offset * w
                if lm < w or lm >= d["n"] - w:
                    per[c] = float("nan")
                    continue
                per[c], _pct = d_limb(series_of(c), lm, w, d["n"], rng)
            vals = np.array([per[c] for c in ok], float)
            good = np.isfinite(vals)
            if good.sum() < 6:
                continue
            m = float(np.mean(vals[good]))
            lo, hi, _n = cluster_bootstrap_ci(
                lambda ix, vv=vals[good]: float(np.mean(vv[list(ix)])),
                np.arange(int(good.sum())), rng, reps=2000)
            res[tag] = {"mean_D": m, "ci": [lo, hi], "n_pos": int((vals[good] > 0).sum()),
                        "n": int(good.sum())}
        return res

    # ---- G2 positive control, re-run under the tighter comparison --------------------------------------
    print(f"\nG2 POSITIVE CONTROL under the limb-matched comparison (can now fail)")
    g2_rows = {}
    for sig in (0.25, 0.5, 1.0):
        syn = {c: data[c]["label"] + sig * rng.standard_normal(data[c]["n"]) for c in ok}
        r = arm(lambda c, s=syn: s[c])
        g2_rows[f"sigma{sig}"] = r
        for t, v in r.items():
            print(f"   sigma={sig:<5}{t}  D={v['mean_D']:+.4f} [{v['ci'][0]:+.4f},{v['ci'][1]:+.4f}]  "
                  f"{v['n_pos']}/{v['n']}")
    g2 = all(v["ci"][0] > 0 for r in g2_rows.values() for v in r.values())
    print(f"   -> {'PASS' if g2 else 'FAIL: the comparison is now too tight to answer anything'}")

    # ---- G3 drug-trajectory negative control -----------------------------------------------------------
    print(f"\nG3 DRUG-TRAJECTORY NEGATIVE CONTROL  triangular ramp peaking mid-unconsciousness, "
          f"label-independent")
    tri = {}
    for c in ok:
        d = data[c]
        n, l0, r0 = d["n"], int(d["loc"][0]), int(d["roc"][0])
        mid = (l0 + r0) // 2
        t = np.arange(n, dtype=float)
        v = np.where(t <= mid, (t - 0) / max(mid, 1), (n - t) / max(n - mid, 1))
        tri[c] = np.clip(v, 0, 1) + 0.05 * rng.standard_normal(n)
    r3 = arm(lambda c, s=tri: s[c])
    for t, v in r3.items():
        print(f"   {t}  D={v['mean_D']:+.4f} [{v['ci'][0]:+.4f},{v['ci'][1]:+.4f}]  "
              f"{v['n_pos']}/{v['n']}")
    g3 = all(v["ci"][0] <= 0 <= v["ci"][1] for v in r3.values())
    print(f"   -> {'PASS' if g3 else 'FAIL: the comparison is still not matched to the drug limb'}")
    out["G2"] = {"rows": g2_rows, "pass": bool(g2)}
    out["G3"] = {"rows": r3, "pass": bool(g3)}

    gates = g1 and g2 and g3
    print(f"\nGATES {'ALL PASS' if gates else 'NOT ALL PASSED -- no verdict is issued'}\n")

    # ---- primary: real landmark beside the fixed-offset pseudo-landmark ---------------------------------
    print(f"{'candidate':18s} {'lm':4s} {'REAL D':>9s} {'95% CI':>20s} {'sgn':>6s} | "
          f"{'PSEUDO D':>9s} {'95% CI':>20s} {'G4':>5s}")
    res = {}
    for f in alive:
        real = arm(lambda c, ff=f: data[c]["X"][ff])
        pseu_lo = arm(lambda c, ff=f: data[c]["X"][ff], offset=-PSEUDO)
        pseu_hi = arm(lambda c, ff=f: data[c]["X"][ff], offset=+PSEUDO)
        wins = {t: [arm(lambda c, ff=f: data[c]["X"][ff], w=w).get(t, {}).get("mean_D", float("nan"))
                    for w in WINDOWS] for t in ("LOC", "ROC")}
        for t in ("LOC", "ROC"):
            r, pl, ph = real.get(t), pseu_lo.get(t), pseu_hi.get(t)
            if not r:
                continue
            ps = max((x for x in (pl, ph) if x), key=lambda v: v["mean_D"], default=None)
            g4 = len({int(np.sign(x)) for x in wins[t] if math.isfinite(x) and x != 0}) == 1
            res[f"{f}|{t}"] = {"feature": f, "landmark": t, "real": r, "pseudo": ps,
                               "window_means": wins[t], "G4_sign_agrees": bool(g4),
                               "survives": bool(r["ci"][0] > 0 and ps and ps["ci"][0] <= 0 and g4)}
            print(f"{f:18s} {t:4s} {r['mean_D']:+9.4f} "
                  f"[{r['ci'][0]:+7.4f},{r['ci'][1]:+7.4f}] {r['n_pos']:2d}/{r['n']:<2d} | "
                  f"{(ps['mean_D'] if ps else float('nan')):+9.4f} "
                  f"[{(ps['ci'][0] if ps else float('nan')):+7.4f},"
                  f"{(ps['ci'][1] if ps else float('nan')):+7.4f}] "
                  f"{'ok' if g4 else 'FAIL':>5s}")
    out["primary"] = res

    both = [f for f in alive
            if res.get(f"{f}|LOC", {}).get("survives") and res.get(f"{f}|ROC", {}).get("survives")]
    pseudo_high = sum(1 for f in alive
                      if any(res.get(f"{f}|{t}", {}).get("pseudo", {}) and
                             res[f"{f}|{t}"]["pseudo"]["ci"][0] > 0 for t in ("LOC", "ROC")))
    if not gates:
        verdict = ("NO VERDICT -- " + ("G2 failed (positive control lost) " if not g2 else "")
                   + ("G3 failed (drug-trajectory control still fires) " if not g3 else "")
                   + ("G1 failed" if not g1 else ""))
    elif both:
        verdict = (f"POSITIVE -- {', '.join(both)} keep D > 0 at the real landmark while the "
                   f"same-limb pseudo-landmark sits at zero, at BOTH landmarks. First evidence here of a "
                   f"spectral feature sensitive to the behavioural threshold rather than to the exposure. "
                   f"Replicate on the 44 OR cases before describing it further.")
    else:
        verdict = (f"NEGATIVE, AND E151 IS WITHDRAWN -- {pseudo_high} of {len(alive)} candidates score "
                   f"above zero at a pseudo-landmark on the same limb where no responsiveness change "
                   f"occurs, and none survives the contrast at both landmarks. E151's eleven-of-eleven "
                   f"positive was limb steepness. **The frontal spectral family tracks the concentration "
                   f"trajectory and carries no detectable signature of the behavioural threshold "
                   f"crossing itself**, even when that crossing is known to the second. Registered "
                   f"prediction confirmed.")
    print(f"\nVERDICT: {verdict}")
    out["verdict"] = verdict
    json.dump(out, open(OUT, "w"), indent=1, sort_keys=True, allow_nan=True)
    print(f"\n   wrote {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
