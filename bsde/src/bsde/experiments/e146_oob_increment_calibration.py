#!/usr/bin/env python3
"""E146 -- what can `oob_regression_increment` actually detect? A calibration, on synthetic data only.

REGISTERED BEFORE ANY CELL OF THE SWEEP HAS BEEN RUN. No deposit is touched. Nothing here is about
consciousness, anaesthesia or any challenge; it is about the instrument that decided several of this
project's null results.

=========================================================================================================
WHY THIS IS SUDDENLY THE MOST LOAD-BEARING THING TO MEASURE
=========================================================================================================
Three consecutive experiments measured a detectability floor and all three came back at **0.0 % detection
for every injected effect up to rho_partial = 0.40**:

    E143   eegmmidb, n = 104 subjects, Bonferroni interval    0 % to 0.40
    E144   eegmmidb, n = 104, one-sided tail fraction         0 % to 0.40   (resolution verified adequate)
    E145   Stieger,  n = 62 subjects / 185 sessions           (running at the time of writing)

E143's zero was partly a Monte Carlo artefact and was diagnosed as such. E144's was not: the decision rule
resolves to 0.00067 against a bar of 0.00156, and the injected effect is constructed to have exactly the
stated partial correlation with the target given the incumbent. **A partial correlation of 0.40 at n = 104
is enormous** -- an ordinary partial-correlation t-test would find it essentially always. So either the
injection is wrong or the instrument is far more conservative than anyone using it has assumed.

**This matters beyond Challenge B.** `oob_regression_increment` and its AUC twin decided E84, E122's P2,
E134 and a number of others. If the instrument cannot see a partial correlation of 0.3, then every one of
those nulls means "we could not have seen it" rather than "it is not there", and rule 40's principle -- a
gate that cannot fail is not a gate -- applies to a whole class of this project's conclusions.

=========================================================================================================
WHAT IS SWEPT
=========================================================================================================
Fully synthetic. An incumbent `a ~ N(0,1)`, a target `y = a + e`, and a candidate `z` constructed as
`rho * r + sqrt(1-rho^2) * noise` where `r` is the standardised residual of y on a -- so `z` has partial
correlation exactly `rho` with `y` given `a`, by construction and not by estimation.

    n_subjects       60, 100, 200
    rows_per_subject 1, 3            (3 exercises the clustering; the cluster is always the subject)
    rho_partial      0.15, 0.25, 0.35, 0.50
    draws            60 per cell
    reps             1,000 out-of-bag bootstrap resamples per call

Two decision rules are scored on every draw, because the project uses both:
    UNCORRECTED   one-sided tail fraction p < 0.05
    CORRECTED     p < 0.05/30, the bar a 30-candidate sweep imposes

=========================================================================================================
THE INDEPENDENT REFERENCE, WHICH IS THE POINT (rule 23)
=========================================================================================================
Every cell is also scored by an **ordinary partial-correlation t-test** -- `t = r_p * sqrt(df) /
sqrt(1-r_p^2)`, df = n_rows - 3 -- computed in closed form with no bootstrap, no resampling and no shared
code. Self-written code checked against self-written code shares blind spots; a closed-form test written
from the textbook formula does not share this one.

The reportable quantity is the **ratio**: at each cell, what fraction of the oracle's power does the
out-of-bag increment retain? That number is reusable by every future registration in this repo and is what
converts "nothing added" into either "nothing is there" or "we could not have seen it".

Note the reference is deliberately generous to itself: it ignores clustering, so at rows_per_subject = 3
it is anticonservative and its power is an upper bound rather than a fair comparator. That is stated so
the ratio is read as "fraction of an optimistic ceiling", not as "fraction of the correct test".

=========================================================================================================
REGISTERED PREDICTIONS -- WRONG-DIRECTION BRANCH FIRST (rule 37)
=========================================================================================================
P1  **At (n = 100, rows = 1, rho = 0.35), the out-of-bag increment detects in under 50 % of draws at the
    UNCORRECTED bar.** If it detects in more than 80 %, the instrument is fine and E143-E145's floors are
    caused by something specific to those cohorts -- most likely that the injected residual `r` there is
    computed against a target whose variance the incumbent barely explains -- and this file will say so
    and hand the problem back to those experiments rather than to the machinery.

P2  **At the same cell the closed-form partial-correlation test detects in over 90 % of draws.** If it
    does not, the effect sizes being called "enormous" are not, my framing above is wrong, and P1 is
    uninterpretable.

P3  **The retained-power ratio falls as the correction gets stricter and as rows_per_subject rises.** The
    second half is the interesting one: clustering shrinks the effective out-of-bag set without shrinking
    the row count, so an instrument that resamples clusters should lose more than the row-level oracle
    does.

GATE. G1 SANITY: at rho_partial = 0 the out-of-bag increment must detect at no more than the nominal rate
(<= 0.10 at the uncorrected bar, over 200 draws). An instrument that fires on a null effect is broken in
the other direction and nothing else here would be interpretable. **This gate can fail and it is checked
before the sweep.**

CONSEQUENCE, WRITTEN BEFORE THE NUMBERS. If P1 and P2 both hold, then every null in this repository
decided by an out-of-bag increment must be re-read against this table, and the ones whose effect sizes sit
below the measured floor must be relabelled from NEGATIVE to ABSENT (rule 31: when a precondition fails,
the downstream verdict is absent, not negative). That relabelling is a separate, named piece of work and
is not done in this file.

    python bsde/src/bsde/experiments/e146_oob_increment_calibration.py
"""
from __future__ import annotations

import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.verifier.stats import oob_regression_increment, spearman             # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e146_oob_increment_calibration.json")

N_SUBJ = (60, 100, 200)
ROWS_PER = (1, 3)
RHOS = (0.15, 0.25, 0.35, 0.50)
DRAWS = 60
REPS = 1000
CORRECTED = 0.05 / 30


def rank_stat(t, p):
    r = spearman(list(np.asarray(t, float)), list(np.asarray(p, float)))
    return -r if math.isfinite(r) else float("nan")


def oracle_p(a, y, z):
    """Closed-form partial correlation t-test, written from the textbook formula. No shared code."""
    A = np.c_[np.ones(len(a)), a]
    ry = y - A @ np.linalg.lstsq(A, y, rcond=None)[0]
    rz = z - A @ np.linalg.lstsq(A, z, rcond=None)[0]
    sy, sz = ry.std(), rz.std()
    if sy < 1e-12 or sz < 1e-12:
        return float("nan")
    r = float(np.mean((ry - ry.mean()) * (rz - rz.mean())) / (sy * sz))
    r = max(min(r, 1 - 1e-12), -1 + 1e-12)
    df = len(a) - 3
    if df <= 0:
        return float("nan")
    t = r * math.sqrt(df) / math.sqrt(1 - r * r)
    # one-sided normal approximation; df >= 57 everywhere in this sweep so the normal tail is adequate
    return 0.5 * math.erfc(t / math.sqrt(2.0))


def one_draw(rng, n_subj, rows_per, rho, reps=REPS):
    n = n_subj * rows_per
    subj = np.repeat(np.arange(n_subj), rows_per)
    a = rng.standard_normal(n)
    y = a + rng.standard_normal(n)
    A = np.c_[np.ones(n), a]
    r = y - A @ np.linalg.lstsq(A, y, rcond=None)[0]
    r = (r - r.mean()) / (r.std() + 1e-12)
    z = rho * r + math.sqrt(max(1 - rho ** 2, 0.0)) * rng.standard_normal(n)
    Xa = a.reshape(-1, 1)
    Xb = np.c_[a, z]
    _m, _lo, _hi, _n, d = oob_regression_increment(Xa, Xb, y, subj, rng, stat=rank_stat, reps=reps,
                                                   return_diffs=True)
    p_oob = float((d >= 0).mean()) if len(d) else float("nan")
    return p_oob, oracle_p(a, y, z)


def main(argv=None) -> int:
    rng = np.random.default_rng(146)
    out = {"experiment": "E146", "n_subj": list(N_SUBJ), "rows_per": list(ROWS_PER),
           "rhos": list(RHOS), "draws": DRAWS, "reps": REPS, "corrected_bar": CORRECTED}

    # ---- G1 SANITY at rho = 0 -------------------------------------------------------------------------
    fp = 0
    for _ in range(200):
        p, _o = one_draw(rng, 100, 1, 0.0, reps=REPS)
        fp += math.isfinite(p) and p < 0.05
    rate = fp / 200
    g1 = rate <= 0.10
    print(f"G1 SANITY  false-positive rate at rho_partial=0, n=100, 200 draws: {rate:.3f} "
          f"(bar <= 0.10) -> {'PASS' if g1 else 'FAIL'}")
    out["G1"] = {"pass": bool(g1), "false_positive_rate": rate}
    if not g1:
        print("\nGATE FAILED -- the instrument fires on a null effect; nothing below is interpretable.")
        json.dump(out, open(OUT, "w"), indent=1, sort_keys=True)
        return 1

    print(f"\n{'n_subj':>7s} {'rows':>5s} {'rho_p':>6s} | {'OOB p<.05':>10s} {'OOB corr':>9s} "
          f"{'ORACLE':>8s} | {'retained':>9s}")
    cells = {}
    for ns in N_SUBJ:
        for rp in ROWS_PER:
            for rho in RHOS:
                hu = hc = ho = 0
                for _ in range(DRAWS):
                    p, o = one_draw(rng, ns, rp, rho)
                    hu += math.isfinite(p) and p < 0.05
                    hc += math.isfinite(p) and p < CORRECTED
                    ho += math.isfinite(o) and o < 0.05
                u, c, orc = hu / DRAWS, hc / DRAWS, ho / DRAWS
                ret = u / orc if orc > 0 else float("nan")
                cells[f"{ns}|{rp}|{rho}"] = {"n_subj": ns, "rows_per": rp, "rho": rho,
                                             "oob_uncorrected": u, "oob_corrected": c,
                                             "oracle": orc, "retained": ret}
                print(f"{ns:7d} {rp:5d} {rho:6.2f} | {u:10.2%} {c:9.2%} {orc:8.2%} | {ret:9.2%}")
    out["cells"] = cells

    key = cells.get("100|1|0.35")
    p1 = ("CONFIRMED -- the out-of-bag increment is far more conservative than assumed"
          if key and key["oob_uncorrected"] < 0.50 else
          "REFUTED -- the instrument detects here, so E143-E145's floors are specific to those cohorts "
          "and the problem goes back to them rather than to the machinery")
    p2 = ("CONFIRMED -- the effect is large by any ordinary standard"
          if key and key["oracle"] > 0.90 else
          "REFUTED -- the closed-form test does not find it either, so P1 is uninterpretable and the "
          "framing above is wrong")
    print(f"\nP1 at (n=100, rows=1, rho=0.35): OOB uncorrected "
          f"{key['oob_uncorrected']:.2%} -> {p1}")
    print(f"P2 at the same cell: oracle {key['oracle']:.2%} -> {p2}")

    r1 = [v["retained"] for v in cells.values() if v["rows_per"] == 1 and v["oracle"] > 0.2]
    r3 = [v["retained"] for v in cells.values() if v["rows_per"] == 3 and v["oracle"] > 0.2]
    p3 = ("CONFIRMED -- clustering costs the out-of-bag instrument more than it costs the row-level oracle"
          if np.nanmean(r3) < np.nanmean(r1) else
          "REFUTED -- clustering does not degrade the instrument relative to the oracle")
    print(f"P3 mean retained power: rows_per=1 {np.nanmean(r1):.2%}, rows_per=3 {np.nanmean(r3):.2%} "
          f"-> {p3}")
    out["P1"], out["P2"], out["P3"] = p1, p2, p3
    out["retained_mean"] = {"rows_per_1": float(np.nanmean(r1)), "rows_per_3": float(np.nanmean(r3))}

    json.dump(out, open(OUT, "w"), indent=1, sort_keys=True, allow_nan=True)
    print(f"\n   wrote {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
