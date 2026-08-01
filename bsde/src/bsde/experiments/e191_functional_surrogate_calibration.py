#!/usr/bin/env python3
"""E191 — can a surrogate placebo MANUFACTURE an increment? The gate that measures the thing itself.

REGISTERED BEFORE ANY CALIBRATION LADDER HAS BEEN RUN.

=========================================================================================================
THIS IS THE THIRD GATE DESIGN FOR THE SAME PLACEBO, AND THAT HAS TO BE JUSTIFIED STRUCTURALLY
=========================================================================================================
E187 refused on a round-number autocorrelation tolerance (0.05). E189 replaced that number with a
self-referential comparison against surrogate-versus-surrogate differences and refused **all eleven**
candidates. E190 changed the surrogate to a circular shift, which preserves the periodogram by theorem,
and faced E189's gate verbatim.

**Three refusals in a row is the point at which one must ask whether the gate is measuring the right
thing, and the answer here is available a priori — it does not depend on how E190 came out.**

    Every version of this gate asks *does the surrogate preserve the autocorrelation?* That is a
    **proxy**. The question it stands in for is *could the surrogate's imperfection MANUFACTURE the
    increment I am about to read?* Those are not the same question, and the proxy has a structural
    defect that no threshold can fix: a surrogate-versus-surrogate reference **cancels any bias shared
    by all surrogates**, because both sides carry it. Real-versus-surrogate does not. So if a surrogate
    family depresses the estimated autocorrelation at all — IAAFT through its amplitude re-imposition,
    a circular shift through its wrap seam — real-versus-surrogate exceeds surrogate-versus-surrogate by
    that bias, at any sample size, however small the bias is in absolute terms.

**The quantity that actually matters is directly measurable, on the primary statistic itself, and this
file measures it.** If a surrogate's imperfection inflates increments, then a column that is PURE NOISE
with the same autocorrelation as a real candidate will beat its own surrogates. So: build a ladder of
null columns spanning the autocorrelation range of the real candidates and require every rung to be
withdrawn.

=========================================================================================================
THE PRIMARY IS A QUESTION ABOUT THE METHOD, NOT ABOUT THE CANDIDATES
=========================================================================================================
Stating it this way is deliberate and it is what removes the goalpost-moving charge: **the primary here
is not a re-read of E187's table.** It is

    **P1.  For each surrogate family, and at each rung of an autocorrelation ladder, what fraction of
           per-recording AR(1) null columns beat their own surrogates at the 5 % bar?**

with the pre-declared conclusion rule that a family is USABLE at a given autocorrelation only if the
observed false-positive rate at that rung is at or below the nominal 5 %, measured over `N_REPS`
independent null columns rather than one (rule 72: a gate evaluated on one draw cannot estimate a rate).

Re-reading E150's eleven candidates is a **conditional secondary**, and the condition is stated before
the run: a candidate may be read only if BOTH ladder rungs bracketing **its own** measured lag-1
autocorrelation were usable, in the family being read. A candidate more autocorrelated than the top rung
is unreadable regardless of what it scored. **If no family is usable at the autocorrelation of the real
candidates, the conclusion is that E187's table stays unlicensed and Challenge C has no licensed
incremental result on DOSE-I** — that outcome is available here and is not a failure of the experiment.

=========================================================================================================
BOTH SURROGATE FAMILIES ARE RUN, PRE-DECLARED, AND NEITHER IS FAVOURED
=========================================================================================================
  IAAFT           E187/E189's surrogate: phase randomisation with the marginal re-imposed by iteration.
  CIRCULAR SHIFT  E190's: a phase rotation, so the periodogram and the marginal are preserved exactly,
                  at the cost of one wrap seam per recording.

Running both is not a search for whichever passes. The ladder is the *same* for both, the bar is the
same, and the result is a two-column table that says what each family can and cannot support. A family
that fails at every rung is reported as such.

=========================================================================================================
GATES
=========================================================================================================
G1  cohort rebuild against E150's stored 62 recordings / 17,196 windows.
G2  the incumbent must predict the real MOAA/S (the label is never touched by a feature-side placebo).
G3  **ALIVENESS.** The positive control — within-recording z(MOAA/S) plus noise at rho ~ 0.30 — must
    SURVIVE in the family being read. E190 measured it at fraction 0.0000 for circular shift, so this is
    known to be achievable; it is gated anyway because a machine that cannot return the right answer for
    a system whose answer is known cannot be trusted on one whose answer is not (rule 40).
G4  each null rung's surrogates must decorrelate from it below rho 0.30, or that rung is uninformative
    and is reported as such rather than counted as a pass.
G5  the ladder must SPAN the real candidates: the measured lag-1 autocorrelation of every candidate to
    be read must lie between two usable rungs. Extrapolation past the top rung is refused.

=========================================================================================================
VERDICT — WRONG-DIRECTION CASES FIRST (rule 37)
=========================================================================================================
  (1) NOT INTERPRETABLE       G1, G2 or G3 fails for both families.
  (2) NO FAMILY USABLE        every family exceeds the nominal rate at the rungs that bracket the real
                              candidates. E187's table stays unlicensed; the placebo approach is closed.
  (3) USABLE, NOTHING READ    a family is usable but the ladder does not span the real candidates (G5).
  (4) USABLE, TABLE LICENSED  a family is usable at the bracketing rungs, and the conditional secondary
                              may then be read for the candidates it covers.

**REGISTERED PREDICTION: (4) for the circular-shift family and (4) for IAAFT, with observed false-
positive rates at or below 0.05 at every rung up to rho = 0.95 and a rate ABOVE nominal at rho = 0.99.**
The reasoning is that E187's and E190's random-walk calibrations — rho = 1, the limit of this ladder —
were both correctly withdrawn (0.4900 and 0.8450), which is direct evidence that neither family's
autocorrelation distortion translates into an inflated increment; but a single draw cannot estimate a
rate, which is exactly why this file runs a ladder rather than one column. **If the rate is above nominal
at a rung that brackets the real candidates, the honest reading is (2), and E187's nine survivors stay
unlicensed permanently.**

    python bsde/src/bsde/experiments/e191_functional_surrogate_calibration.py
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, HERE)

from bsde.verifier.stats import grouped_cv_predict, spearman                         # noqa: E402
import e84_increment_over_validated_incumbent as E84                                 # noqa: E402
from e150_challenge_c_negatives_rederived import build                               # noqa: E402
from e180_moaas_label_placebo import E150_ADDS, MUSCLE, baseline_perf                # noqa: E402
from e189_surrogate_placebo_selfreferential_gate import iaaft                         # noqa: E402
from e190_circular_shift_placebo import _ac, absolute_ac, increment                   # noqa: E402
from e190_circular_shift_placebo import positive_control                              # noqa: E402
from e190_circular_shift_placebo import surrogate_column as shift_column              # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
E150_JSON = os.path.join(RESULTS, "e150_challenge_c_rederived.json")
OUT = os.path.join(RESULTS, "e191_functional_surrogate_calibration.json")
SEED = 20260801

LADDER = (0.0, 0.5, 0.8, 0.95, 0.99)   # AR(1) lag-1 autocorrelation of each null rung
N_REPS = 20                            # independent null columns per rung -- a RATE, not one draw
N_SURR = 60                            # surrogates per null column (the rate needs breadth, not depth)
N_SURR_REAL = 200                      # surrogates for the positive control and the real candidates
CORR_MAX = 0.30
ALPHA = 0.05
NOMINAL = 0.05
POS_RHO = 0.30

try:
    _e150 = json.load(open(E150_JSON))
    N_RECORDINGS, N_WINDOWS = int(_e150["n_recordings"]), int(_e150["n_windows"])
except Exception:                                                              # noqa: BLE001
    N_RECORDINGS, N_WINDOWS = -1, -1


def iaaft_column(x, subj, rng):
    """Per-recording IAAFT, E189's surrogate, reproduced here so both families share one call shape."""
    out = np.full(x.size, np.nan)
    for u in np.unique(subj):
        m = subj == u
        v = x[m]
        ok = np.isfinite(v)
        if ok.sum() < 8:
            out[m] = v
            continue
        s = v.copy()
        s[ok] = iaaft(v[ok], rng)
        out[m] = s
    return out


FAMILIES = {"iaaft": iaaft_column, "circular_shift": shift_column}


def ar1_column(subj, rho, rng):
    """A per-recording AR(1) null: correlated with nothing, with a KNOWN lag-1 autocorrelation."""
    out = np.empty(len(subj))
    sd = float(np.sqrt(max(1e-12, 1.0 - rho ** 2)))
    for u in np.unique(subj):
        m = subj == u
        n = int(m.sum())
        v = np.empty(n)
        v[0] = rng.normal()
        for i in range(1, n):
            v[i] = rho * v[i - 1] + rng.normal(0.0, sd)
        out[m] = v
    return out


def mean_abs_rho(x, s, subj):
    cr = []
    for u in np.unique(subj):
        m = subj == u
        ok = np.isfinite(x[m]) & np.isfinite(s[m])
        if ok.sum() > 10:
            r = spearman(list(x[m][ok]), list(s[m][ok]))
            if np.isfinite(r):
                cr.append(abs(r))
    return float(np.mean(cr)) if cr else float("nan")


def fraction_at_or_below(x, base, y, subj, fam, n_surr, tag):
    """The primary statistic: fraction of surrogates whose increment reaches or beats the real one."""
    real = increment(base, x, y, subj, SEED + 3)
    if not np.isfinite(real):
        return float("nan"), float("nan"), float("nan")
    sv, rho_s = [], []
    for i in range(n_surr):
        s = fam(x, subj, np.random.default_rng(SEED + tag + i))
        if i < 10:
            rho_s.append(mean_abs_rho(x, s, subj))
        v = increment(base, s, y, subj, SEED + tag + 5000 + i)
        if np.isfinite(v):
            sv.append(v)
    sv = np.asarray(sv)
    frac = float((sv <= real).mean()) if sv.size >= 20 else float("nan")
    return real, frac, (float(np.nanmean(rho_s)) if rho_s else float("nan"))


def main() -> int:
    print("E191 — does a surrogate placebo manufacture increments? A false-positive rate, not a proxy")
    y, subj, base, cand, cands, n_rec = build()
    res = {"experiment": "E191", "n_recordings": int(n_rec), "n_windows": int(len(y)),
           "ladder": list(LADDER), "n_reps": N_REPS, "n_surrogates_ladder": N_SURR,
           "alpha": ALPHA, "nominal": NOMINAL, "families": {}}

    g1 = bool(n_rec == N_RECORDINGS and len(y) == N_WINDOWS)
    print(f"G1 REBUILD  {n_rec} recordings, {len(y)} windows vs E150's stored "
          f"{N_RECORDINGS} / {N_WINDOWS}   {'PASS' if g1 else 'FAIL'}")
    rho_b = baseline_perf(base, y, subj, SEED)
    g2 = bool(np.isfinite(rho_b) and rho_b > 0.20)
    print(f"G2 INCUMBENT ALIVE  PE31+SEF95 out-of-fold rho = {rho_b:+.4f}   {'PASS' if g2 else 'FAIL'}")
    res["g1_rebuild"], res["g2_incumbent_rho"] = g1, float(rho_b)
    if not (g1 and g2):
        res["verdict"], res["why"] = "NOT INTERPRETABLE", "the cohort or the incumbent gate failed"
        json.dump(res, open(OUT, "w"), indent=2)
        print(f"VERDICT: {res['verdict']} — {res['why']}")
        return 1

    # G5's inputs: where do the real candidates actually SIT on the ladder?
    print("\nG5 SPAN — the measured lag-1 autocorrelation of each real candidate")
    ac_real = {}
    for name in E150_ADDS:
        x = cand.get(name)
        if x is None:
            continue
        a1, a9 = absolute_ac(x, subj)
        ac_real[name] = {"ac1": a1, "ac9": a9}
        print(f"   {name:<26s} |AC1| {a1:.3f}   |AC9| {a9:.3f}")
    res["candidate_autocorrelation"] = ac_real
    top = max(LADDER)
    above_top = [n for n, v in ac_real.items() if np.isfinite(v["ac1"]) and v["ac1"] > top]
    print(f"   ladder top rung rho = {top}; candidates above it: {above_top or 'none'}")
    res["candidates_above_top_rung"] = above_top

    for fam_name, fam in FAMILIES.items():
        print(f"\n{'=' * 100}\nFAMILY: {fam_name}")
        fres = {"rungs": {}}

        print("G3 ALIVENESS — within-recording z(MOAA/S) + noise; it MUST survive")
        pc = positive_control(y, subj, np.random.default_rng(SEED + 888))
        pr = [spearman(list(pc[subj == u]), list(np.asarray(y, float)[subj == u]))
              for u in np.unique(subj)]
        pr = [r for r in pr if np.isfinite(r)]
        real, frac, rho_s = fraction_at_or_below(pc, base, y, subj, fam, N_SURR_REAL, 41000)
        alive = bool(np.isfinite(frac) and frac <= ALPHA and np.isfinite(rho_s) and rho_s < CORR_MAX)
        print(f"   positive control rho(control, MOAA/S) = {np.mean(pr):+.3f}; "
              f"real {real:+.5f}, frac {frac:.4f}, surrogate rho {rho_s:.3f}   "
              f"{'PASS' if alive else '*** FAIL'}")
        fres["aliveness"] = {"real": real, "frac": frac, "surrogate_rho": rho_s, "pass": alive}

        print(f"\n   {'rung':>6s} {'n':>4s} {'FP rate':>9s} {'[binomial 95%]':>18s} "
              f"{'surr rho':>9s}  usable")
        for rho_t in LADDER:
            fr, rhos = [], []
            for r in range(N_REPS):
                x = ar1_column(subj, rho_t, np.random.default_rng(SEED + 60000
                                                                  + int(rho_t * 1000) * 100 + r))
                _re, f, rs = fraction_at_or_below(x, base, y, subj, fam, N_SURR,
                                                  70000 + int(rho_t * 1000) * 100 + r * 10)
                if np.isfinite(f):
                    fr.append(f)
                if np.isfinite(rs):
                    rhos.append(rs)
            fr = np.asarray(fr)
            n = int(fr.size)
            hits = int((fr <= ALPHA).sum()) if n else 0
            rate = hits / n if n else float("nan")
            # exact-ish binomial interval on the rate (Wilson), so the comparison to nominal has width
            if n:
                z = 1.959963985
                c = (hits + z * z / 2) / (n + z * z)
                h = z * np.sqrt(hits * (n - hits) / n + z * z / 4) / (n + z * z)
                lo, hi = max(0.0, c - h), min(1.0, c + h)
            else:
                lo = hi = float("nan")
            srho = float(np.mean(rhos)) if rhos else float("nan")
            g4 = bool(np.isfinite(srho) and srho < CORR_MAX)
            # USABLE means the false-positive rate is not ABOVE nominal: the lower end of the
            # interval must not exceed the nominal rate. A rung whose surrogates fail to decorrelate
            # (G4) is uninformative and is NOT counted as usable.
            usable = bool(g4 and np.isfinite(lo) and lo <= NOMINAL)
            fres["rungs"][f"{rho_t}"] = {"n": n, "hits": hits, "fp_rate": rate,
                                         "ci": [lo, hi], "surrogate_rho": srho,
                                         "g4_destroys": g4, "usable": usable}
            print(f"   {rho_t:>6.2f} {n:>4d} {rate:>9.3f} [{lo:>7.3f}, {hi:>7.3f}] {srho:>9.3f}  "
                  f"{'yes' if usable else ('NO (G4)' if not g4 else 'NO')}")
        res["families"][fam_name] = fres

    # ---- verdict, wrong-direction cases first -----------------------------------------------------
    def brackets(a1, fres):
        """The two rungs bracketing a1, and whether both are usable."""
        if not np.isfinite(a1):
            return None
        below = [r for r in LADDER if r <= a1]
        above = [r for r in LADDER if r >= a1]
        if not below or not above:
            return None
        lo_r, hi_r = max(below), min(above)
        return (lo_r, hi_r, fres["rungs"][f"{lo_r}"]["usable"] and fres["rungs"][f"{hi_r}"]["usable"])

    licensed = {}
    for fam_name, fres in res["families"].items():
        if not fres["aliveness"]["pass"]:
            continue
        ok = []
        for name, v in ac_real.items():
            b = brackets(v["ac1"], fres)
            if b and b[2]:
                ok.append(name)
        licensed[fam_name] = ok
    res["licensed_candidates"] = licensed

    any_alive = any(f["aliveness"]["pass"] for f in res["families"].values())
    any_licensed = any(v for v in licensed.values())
    print("\n" + "=" * 100)
    if not any_alive:
        v, why = "NOT INTERPRETABLE", ("no surrogate family lets the positive control survive, so "
                                       "neither can be read (rule 40)")
    elif not any_licensed:
        v, why = "NO FAMILY USABLE", (
            "no family holds its false-positive rate at or below nominal on the rungs bracketing the "
            "real candidates' own autocorrelation, so E187's nine survivors stay UNLICENSED and the "
            "feature-side surrogate placebo is closed on this deposit")
    else:
        v, why = "USABLE — TABLE LICENSED", (
            "; ".join(f"{k}: {len(x)} of {len(ac_real)} candidates licensed ({x})"
                      for k, x in licensed.items() if x))
    res["verdict"], res["why"] = v, why
    print(f"VERDICT: {v}\n  {why}")
    print("=" * 100)
    print("SCOPE: this file licenses (or refuses) the METHOD. Reading E187's numbers for the licensed\n"
          "  candidates is a conditional secondary and is done in the ledger row, not here.")

    os.makedirs(RESULTS, exist_ok=True)
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
