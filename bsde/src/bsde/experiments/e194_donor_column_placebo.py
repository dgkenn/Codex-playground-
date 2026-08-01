#!/usr/bin/env python3
"""E194 — the placebo with nothing to distort: a REAL column from a DIFFERENT patient.

REGISTERED BEFORE ANY DONOR COLUMN HAS BEEN DRAWN.

=========================================================================================================
WHY THE SURROGATE APPROACH IS CLOSED, AND WHAT THE QUESTION STILL IS
=========================================================================================================
E187, E189 and E190 all tried to ask one question — **is E150's increment explained by the candidate's own
trend and autocorrelation, or does it need the candidate's alignment with THIS patient's MOAA/S?** — by
manufacturing a synthetic column with the same spectrum and a randomised phase. E191 then measured what
those placebos actually do, on an AR(1) ladder of pure-noise columns, and closed the approach:

    rung (lag-1 AC)   0.00    0.50    0.80    0.95    0.99
    circular shift    0.050   0.100   0.150   0.050   0.250      <- false-positive rate at a 5 % bar

**At rho = 0.80 a column that is pure noise beats its own circular-shift surrogates 15 % of the time, and
at rho = 0.99, 25 %.** The eleven real candidates have measured lag-1 autocorrelation between 0.678 and
0.955, so every one of them is bracketed by a rung the family cannot hold. E187's nine survivors are
unlicensed and stay that way.

The question is not closed, only that way of asking it. **A surrogate is an attempt to synthesise a column
that is realistic in trend and autocorrelation. There is no need to synthesise one — the deposit is full of
them.**

=========================================================================================================
THE DONOR PLACEBO
=========================================================================================================
For each recording, the candidate column is replaced by a **random contiguous block of the SAME candidate
taken from a DIFFERENT recording**, of exactly the required length. Nothing is generated, interpolated,
resampled or phase-randomised:

  * the donor block is a real measurement, so its autocorrelation, marginal, drift, non-stationarity,
    artefact bursts and electrode-drift structure are all whatever this measure genuinely looks like —
    there is no preservation gate to pass because there is no distortion to gate (rules 55, 63);
  * it carries no information about the recipient's MOAA/S, because it came from another patient;
  * a contiguous block is used rather than a resampling so there is no seam and no time-warp. E190's
    circular shift had exactly one seam per recording and that was enough to fail its own gate.

**What this placebo destroys, and what it therefore tests.** A donor block replaces the recipient's
recording-level mean as well as its timing, so between-recording association is destroyed along with
within-recording alignment. That makes this a placebo for the WHOLE association, not only for the timing —
a stricter destruction than E187's, and a different estimand from it. It is declared here rather than
discovered: a candidate withdrawn by this placebo is one whose increment can be reproduced by a plausible
EEG-shaped column from an unrelated patient.

=========================================================================================================
THE CALIBRATION IS THE PRIMARY, EXACTLY AS IN E191
=========================================================================================================
The donor placebo is not assumed to be better because the argument for it is nicer. **It faces E191's
ladder first, unchanged** — the same five AR(1) rungs, the same twenty independent null columns per rung,
the same 5 % bar, the same Wilson interval, the same "usable only if the lower bound does not exceed
nominal" rule — and a candidate is readable only if both rungs bracketing its own measured lag-1
autocorrelation are usable in this family.

    **P1  the donor family's false-positive rate at each rung.**
    P2  (conditional on P1) the eleven candidates' fractions, read only for candidates the ladder covers.

Note which way the risk runs. A donor column from another patient may be *harder* to beat than a surrogate,
because it has real physiological structure; if so the false-positive rate will be at or below nominal and
the ladder will license it. It may equally be *easier* — donor blocks differ from the recipient in scale,
which a cross-fitted model may find uninformative in a way that inflates the apparent increment. **The
ladder measures which, and neither outcome is assumed.**

=========================================================================================================
GATES
=========================================================================================================
G1  cohort rebuild against E150's stored 62 recordings / 17,196 windows.
G2  the incumbent must predict the real MOAA/S.
G3  **ALIVENESS**: the positive control — within-recording z(MOAA/S) plus noise at rho ~ 0.30 — must
    survive (rule 40). It survived in both surrogate families at fraction 0.0000, so failure here would
    indicate the donor placebo destroys real signal, which is a real possible outcome for a placebo this
    aggressive.
G4  a donor block must be uncorrelated with the column it replaces, below rho 0.30. Unlike the surrogate
    families this should hold trivially — it is a different patient — and it is gated because a
    trivially-passing check that is *not verified* is how E22 and E29 shipped gates that could not fail.
G5  **DONOR AVAILABILITY**: every recording needs at least `MIN_DONORS` other recordings long enough to
    supply a block. Reported, not assumed.

=========================================================================================================
VERDICT — WRONG-DIRECTION CASES FIRST (rule 37)
=========================================================================================================
  (1) NOT INTERPRETABLE   G1, G2, G3, G4 or G5 fails.
  (2) NOT CALIBRATED      the ladder's false-positive rate exceeds nominal at the rungs bracketing the
                          real candidates. The donor placebo joins the surrogates as unusable and
                          **Challenge C has no licensed way to ask this question on DOSE-I.**
  (3) ALL WITHDRAWN       calibrated, and no candidate beats its donor distribution.
  (4) MUSCLE ONLY         calibrated, and only the muscle candidates survive.
  (5) SURVIVES            calibrated, and at least one non-muscle candidate beats its donor distribution.

**REGISTERED PREDICTION: (2) NOT CALIBRATED is the outcome I consider most likely at the top rung and
least likely at the middle ones**, so the concrete prediction is a ladder that is usable at rho <= 0.95 and
fails at 0.99, which would license eight of the eleven candidates and refuse `bis_rbr` (|AC1| 0.955). On
the candidates it licenses I predict (5), because E187's and E190's tables both put nine candidates at
fraction 0.0000 with surrogate means near zero. **That prediction is worth recording precisely because the
unlicensed tables are the only evidence for it, and if the donor placebo disagrees with both surrogate
families the surrogates were the problem all along.**

    python bsde/src/bsde/experiments/e194_donor_column_placebo.py
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, HERE)

from bsde.verifier.stats import spearman                                             # noqa: E402
from e150_challenge_c_negatives_rederived import build                               # noqa: E402
from e180_moaas_label_placebo import E150_ADDS, MUSCLE, baseline_perf                # noqa: E402
from e190_circular_shift_placebo import absolute_ac, increment, positive_control     # noqa: E402
from e191_functional_surrogate_calibration import (LADDER, N_REPS, ar1_column,       # noqa: E402
                                                   fraction_at_or_below, mean_abs_rho)

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
E150_JSON = os.path.join(RESULTS, "e150_challenge_c_rederived.json")
OUT = os.path.join(RESULTS, "e194_donor_column_placebo.json")
SEED = 20260801

N_SURR = 60          # donors per null column on the ladder
N_SURR_REAL = 200    # donors per real candidate and for the positive control
CORR_MAX = 0.30
ALPHA = 0.05
NOMINAL = 0.05
MIN_DONORS = 5

try:
    _e150 = json.load(open(E150_JSON))
    N_RECORDINGS, N_WINDOWS = int(_e150["n_recordings"]), int(_e150["n_windows"])
except Exception:                                                              # noqa: BLE001
    N_RECORDINGS, N_WINDOWS = -1, -1


def donor_column(x, subj, rng):
    """Replace each recording's column with a contiguous block of the SAME column from ANOTHER one.

    No generation, no interpolation, no phase randomisation and no seam: the block is a real stretch of
    a real recording. Donors must be at least as long as the recipient; if none is, the longest available
    donor is tiled from its start, which is reported by `n_short` rather than passed over.
    """
    us = list(np.unique(subj))
    idx = {u: np.flatnonzero(subj == u) for u in us}
    out = np.full(x.size, np.nan)
    n_short = 0
    for u in us:
        i = idx[u]
        n = i.size
        pool = [v for v in us if v != u and idx[v].size >= n]
        if pool:
            v = pool[int(rng.integers(len(pool)))]
            j = idx[v]
            s = int(rng.integers(0, j.size - n + 1))
            out[i] = x[j[s:s + n]]
        else:
            n_short += 1
            v = max((w for w in us if w != u), key=lambda w: idx[w].size)
            j = idx[v]
            reps = int(np.ceil(n / j.size))
            out[i] = np.tile(x[j], reps)[:n]
    return out, n_short


def _donor(x, subj, rng):
    return donor_column(x, subj, rng)[0]


def donor_availability(subj):
    us = list(np.unique(subj))
    sz = {u: int((subj == u).sum()) for u in us}
    per = {u: sum(1 for v in us if v != u and sz[v] >= sz[u]) for u in us}
    return per, int(min(per.values())) if per else 0


def main() -> int:
    print("E194 — the donor-column placebo: a real column from a different patient")
    y, subj, base, cand, cands, n_rec = build()
    res = {"experiment": "E194", "n_recordings": int(n_rec), "n_windows": int(len(y)),
           "ladder": list(LADDER), "n_reps": N_REPS, "alpha": ALPHA, "nominal": NOMINAL,
           "placebo": "contiguous block of the same candidate from a different recording"}

    g1 = bool(n_rec == N_RECORDINGS and len(y) == N_WINDOWS)
    print(f"G1 REBUILD  {n_rec} recordings, {len(y)} windows vs E150's stored "
          f"{N_RECORDINGS} / {N_WINDOWS}   {'PASS' if g1 else 'FAIL'}")
    rho_b = baseline_perf(base, y, subj, SEED)
    g2 = bool(np.isfinite(rho_b) and rho_b > 0.20)
    print(f"G2 INCUMBENT ALIVE  PE31+SEF95 out-of-fold rho = {rho_b:+.4f}   {'PASS' if g2 else 'FAIL'}")
    res["g1_rebuild"], res["g2_incumbent_rho"] = g1, float(rho_b)

    per, worst = donor_availability(subj)
    g5 = bool(worst >= MIN_DONORS)
    print(f"G5 DONOR AVAILABILITY  worst recording has {worst} donors at least as long "
          f"(floor {MIN_DONORS}); median {int(np.median(list(per.values())))}   "
          f"{'PASS' if g5 else '*** FAIL'}")
    res["g5_min_donors"], res["g5"] = worst, g5
    if not (g1 and g2 and g5):
        res["verdict"], res["why"] = "NOT INTERPRETABLE", "a cohort or availability gate failed"
        json.dump(res, open(OUT, "w"), indent=2)
        print(f"VERDICT: {res['verdict']} — {res['why']}")
        return 1

    print("\nG3 ALIVENESS — within-recording z(MOAA/S) + noise; it MUST survive")
    pc = positive_control(y, subj, np.random.default_rng(SEED + 888))
    real, frac, rho_s = fraction_at_or_below(pc, base, y, subj, _donor, N_SURR_REAL, 41000)
    g3 = bool(np.isfinite(frac) and frac <= ALPHA)
    g4 = bool(np.isfinite(rho_s) and rho_s < CORR_MAX)
    print(f"   real {real:+.5f}, frac {frac:.4f}, donor-vs-real rho {rho_s:.3f}   "
          f"G3 {'PASS' if g3 else '*** FAIL'}   G4 {'PASS' if g4 else '*** FAIL'}")
    res["aliveness"] = {"real": real, "frac": frac, "donor_rho": rho_s, "g3": g3, "g4": g4}

    print("\nG5' SPAN — measured lag-1 autocorrelation of each real candidate")
    ac_real = {}
    for name in E150_ADDS:
        x = cand.get(name)
        if x is None:
            continue
        a1, a9 = absolute_ac(x, subj)
        ac_real[name] = {"ac1": a1, "ac9": a9}
        print(f"   {name:<26s} |AC1| {a1:.3f}   |AC9| {a9:.3f}")
    res["candidate_autocorrelation"] = ac_real

    print(f"\nP1 CALIBRATION LADDER (donor family)\n   {'rung':>6s} {'n':>4s} {'FP rate':>9s} "
          f"{'[binomial 95%]':>18s} {'donor rho':>10s}  usable")
    rungs = {}
    for rho_t in LADDER:
        fr, rhos = [], []
        for r in range(N_REPS):
            x = ar1_column(subj, rho_t, np.random.default_rng(SEED + 60000
                                                              + int(rho_t * 1000) * 100 + r))
            _re, f, rs = fraction_at_or_below(x, base, y, subj, _donor, N_SURR,
                                              70000 + int(rho_t * 1000) * 100 + r * 10)
            if np.isfinite(f):
                fr.append(f)
            if np.isfinite(rs):
                rhos.append(rs)
        fr = np.asarray(fr)
        n = int(fr.size)
        hits = int((fr <= ALPHA).sum()) if n else 0
        rate = hits / n if n else float("nan")
        if n:
            z = 1.959963985
            c = (hits + z * z / 2) / (n + z * z)
            h = z * np.sqrt(hits * (n - hits) / n + z * z / 4) / (n + z * z)
            lo, hi = max(0.0, c - h), min(1.0, c + h)
        else:
            lo = hi = float("nan")
        drho = float(np.mean(rhos)) if rhos else float("nan")
        ok_rho = bool(np.isfinite(drho) and drho < CORR_MAX)
        usable = bool(ok_rho and np.isfinite(lo) and lo <= NOMINAL)
        rungs[f"{rho_t}"] = {"n": n, "hits": hits, "fp_rate": rate, "ci": [lo, hi],
                             "donor_rho": drho, "g4_destroys": ok_rho, "usable": usable}
        print(f"   {rho_t:>6.2f} {n:>4d} {rate:>9.3f} [{lo:>7.3f}, {hi:>7.3f}] {drho:>10.3f}  "
              f"{'yes' if usable else ('NO (G4)' if not ok_rho else 'NO')}")
    res["rungs"] = rungs

    def brackets(a1):
        if not np.isfinite(a1):
            return None
        below = [r for r in LADDER if r <= a1]
        above = [r for r in LADDER if r >= a1]
        if not below or not above:
            return None
        lo_r, hi_r = max(below), min(above)
        return lo_r, hi_r, (rungs[f"{lo_r}"]["usable"] and rungs[f"{hi_r}"]["usable"])

    licensed = [n for n, v in ac_real.items()
                if (brackets(v["ac1"]) or (None, None, False))[2]]
    res["licensed_candidates"] = licensed
    print(f"\n   licensed by the ladder: {licensed or 'NONE'}")

    table = {}
    if licensed and g3 and g4:
        print(f"\nP2 CANDIDATES (licensed only)\n   {'candidate':<26s} {'real':>10s} "
              f"{'donor mean':>11s} {'frac':>8s}  verdict")
        for name in E150_ADDS:
            if name not in licensed:
                continue
            x = cand[name]
            real, frac, rho_s = fraction_at_or_below(x, base, y, subj, _donor, N_SURR_REAL,
                                                     81000 + 13 * len(table))
            dm = float("nan")
            table[name] = {"real": real, "frac": frac, "donor_rho": rho_s,
                           "withdrawn": bool(np.isfinite(frac) and frac > ALPHA),
                           "muscle": name in MUSCLE}
            print(f"   {name:<26s} {real:>+10.5f} {dm:>11} {frac:>8.4f}  "
                  f"{'WITHDRAWN' if table[name]['withdrawn'] else 'survives'}"
                  + ("   MUSCLE" if name in MUSCLE else ""))
    res["table"] = table

    surv = [n for n, v in table.items() if not v["withdrawn"]]
    non_muscle = [n for n in surv if n not in MUSCLE]
    print("\n" + "=" * 100)
    if not (g3 and g4):
        v, why = "NOT INTERPRETABLE", (
            "the positive control did not survive the donor placebo, or donor blocks were not "
            "independent of the columns they replaced" if not g3 else
            "donor blocks were correlated with the columns they replaced")
    elif not licensed:
        v, why = "NOT CALIBRATED", (
            "the donor placebo's false-positive rate exceeds nominal at the rungs bracketing every "
            "real candidate's own autocorrelation; it joins the surrogate families as unusable and "
            "Challenge C has no licensed way to ask this question on DOSE-I")
    elif not surv:
        v, why = "ALL WITHDRAWN", (
            f"of {len(licensed)} licensed candidates none beats a real column drawn from another "
            "patient, so each increment is reproducible by a plausibly-shaped unrelated series")
    elif not non_muscle:
        v, why = "MUSCLE ONLY", f"only muscle candidates survive: {surv}"
    else:
        v, why = "SURVIVES", (
            f"{len(surv)} of {len(licensed)} licensed candidates beat their donor distribution, "
            f"{len(non_muscle)} non-muscle: {non_muscle}")
    res["verdict"], res["why"] = v, why
    print(f"VERDICT: {v}\n  {why}")
    print("=" * 100)
    print("SCOPE, declared at registration: a donor block replaces the recipient's recording-level mean\n"
          "  as well as its timing, so this is a placebo for the WHOLE association and a STRICTER\n"
          "  destruction than E187's. WITHDRAWN here means 'reproducible by an unrelated patient's\n"
          "  column of the same measure'.")

    os.makedirs(RESULTS, exist_ok=True)
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
