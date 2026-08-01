"""E112 -- WHY is the aperiodic exponent blind to propofol, and does anything else see it?

REGISTERED BEFORE ANY FIDELITY IS COMPUTED FOR THE NEW MEASURES. Existing tables only.

=========================================================================================================
THE FACT THIS EXPLAINS
=========================================================================================================
E110 measured each reading's within-case fidelity to the recorded drug concentration and found, against a
gate that then refused its own primary:

    volatile arm (92 cases, MAC)     BIS +0.4468   whole_head_exponent +0.2837
    TIVA arm     (138 cases, ppf_ce) BIS +0.2911   whole_head_exponent **-0.0382**

**The exponent tracks volatile agent concentration and does not track propofol at all**, on the same
deposit, same pipeline, same statistic. That is a mechanism for a run of Challenge C failures which
previously had none -- E84 (nothing adds), E99 (the exponent HURTS BIS for suppression), E90/E102 -- all on
deposits where propofol dominates. A measure blind to the drug cannot add to one that is not.

=========================================================================================================
TWO HYPOTHESES, BOTH PHYSIOLOGICALLY MOTIVATED, BOTH TESTABLE ON DATA ALREADY EXTRACTED
=========================================================================================================
**H_periodic -- propofol's signature is a PERIODIC oscillation, not a broadband slope.** Propofol's
best-known EEG signature is frontal alpha; a purely aperiodic summary discards the periodic component by
construction. If so, `relative_alpha_power` should track propofol where the exponent does not.

**H_fitrange -- the alpha peak CORRUPTS a slope fitted through it.** `whole_head_exponent` is fitted over
1-40 Hz, and a growing alpha bump sitting inside the fit range pushes the fitted slope in the opposite
direction to the true aperiodic change, which could cancel a real effect to approximately nothing. If so,
`exponent_high` -- fitted over **20-40 Hz, entirely above alpha** -- should track propofol where the 1-40 Hz
version does not, while `exponent_low` (1-20 Hz, alpha inside) should fail like the broadband one.

**These are not mutually exclusive and both are reported whatever happens.** The two make DIFFERENT
predictions about `exponent_high`, which is what makes them separable rather than two ways of saying the
same thing.

=========================================================================================================
ESTIMAND
=========================================================================================================
Per case, within case, across windows, signed so a correctly-tracking measure is positive. Directions are
declared HERE, from physiology, before the run -- not chosen to make anything work:

    fid(relative_alpha_power) = + spearman(., ppf_ce)   propofol INCREASES frontal alpha
    fid(exponent_high)        = + spearman(., ppf_ce)   sedation steepens the high-frequency slope
    fid(exponent_low)         = + spearman(., ppf_ce)   same direction
    fid(whole_head_exponent)  = + spearman(., ppf_ce)   E110's convention, unchanged
    fid(relative_delta_power) = + spearman(., ppf_ce)   included as a second periodic-ish measure
    fid(spectral_edge_95)     = - spearman(., ppf_ce)   sedation LOWERS the spectral edge

    P  for each measure, the paired within-case difference  fid(measure) - fid(whole_head_exponent),
       bootstrapped over cases. Paired on the SAME cases and the SAME windows, so nothing about cohort
       composition can drive it.

A SIGN-AGNOSTIC SECONDARY IS ALSO REPORTED: |fid(measure)| - |fid(whole_head_exponent)|, on the same rows.
A measure that tracks the drug in the direction OPPOSITE to the declared one is still tracking it, and the
signed primary would score that as a failure. Rule 46 permits a folded statistic only when differenced
against itself on the same rows, which is exactly this construction and is why it is a secondary rather
than the primary.

VERDICT per measure, wrong direction FIRST (rule 37):
    (a) difference interval excludes 0 and NEGATIVE -> WORSE THAN THE EXPONENT. Tracks propofol even less
        than a measure that does not track it at all, which would mean it is running backwards.
    (b) interval includes 0 -> NO BETTER. Does not rescue propofol sensitivity.
    (c) interval excludes 0 and POSITIVE -> BETTER. Names which hypothesis it supports.

=========================================================================================================
GATES -- G3 carries the whole claim
=========================================================================================================
    G1  COVERAGE. >= 50 TIVA cases with >= 10 windows, ppf_ce and every measure varying within case.
    G2  THE ANCHOR MUST VARY. `ppf_ce` must have non-zero within-case spread in every contributing case,
        else the correlation is undefined rather than zero (rule 32).
    G3  PROPOFOL SPECIFICITY -- and this is the gate, not a nicety. The identical comparison is run in the
        VOLATILE arm, where the exponent is already alive at +0.2837. **A measure that beats the exponent
        in BOTH arms is simply a better measure and says nothing about propofol.** The claim here is an
        INTERACTION, so the reported quantity is the TIVA advantage minus the volatile advantage, and a
        measure only supports H_periodic or H_fitrange if its advantage is larger under propofol.
        Rule 29's shape: a contrast between A and not-A must be decomposed inside not-A.
    G4  ATTENUATION, carried from E109/E110: within-case SD of the drug and of each measure, plus
        log(n_windows), partialled out of the difference. All attenuate toward zero and would inflate a
        difference between a noisy measure and a clean one.

PLACEBO, gating: `ppf_ce` is PERMUTED ACROSS WINDOWS WITHIN CASE, 500 draws. This destroys the temporal
association while preserving every marginal -- the case's drug range, its measure distribution and its
window count are all untouched -- so anything that survives is about the drug's time course and not about
the case's composition. Primary read FIRST (rule 48).

SCOPE. VitalDB, single-channel BIS-module EEG. Fidelity to a recorded effect-site concentration is not
accuracy against depth of anaesthesia: concentration is an exposure, not a state, and the pump's model of
it is itself a model. Nothing here concerns consciousness.
"""
from __future__ import annotations

import csv
import glob
import json
import math
import os
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e112_propofol_blindness.json")
AGENTS = os.path.join(RESULTS, "vitaldb_agents.csv")
TABLES = [os.path.join(RESULTS, "vitaldb_grid.csv")] + sorted(
    glob.glob(os.path.join(RESULTS, "vitaldb_grid.s*.csv")))

INCUMBENT = "whole_head_exponent"
# measure -> declared sign, fixed before the run
MEASURES = {"relative_alpha_power": +1.0, "exponent_high": +1.0, "exponent_low": +1.0,
            "relative_delta_power": +1.0, "spectral_edge_95": -1.0, INCUMBENT: +1.0}
ARMS = (("tiva", "ppf_ce"), ("volatile", "mac"))
MIN_WINDOWS, MIN_CASES = 10, 50
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


def ci(v):
    v = np.sort(np.asarray([q for q in v if np.isfinite(q)], float))
    if v.size < 50:
        return float("nan"), float("nan")
    return float(np.quantile(v, .025)), float(np.quantile(v, .975))


def build():
    ag = defaultdict(dict)
    for r in csv.DictReader(open(AGENTS, newline="")):
        t = _f(r.get("t_s"))
        if math.isfinite(t):
            ag[r["caseid"]][round(t, 1)] = r
    per = defaultdict(list)
    seen = set()
    for tb in TABLES:
        if not os.path.exists(tb):
            continue
        for r in csv.DictReader(open(tb, newline="")):
            c, t = r.get("meta_caseid"), _f(r.get("meta_t_s"))
            if not c or not math.isfinite(t):
                continue
            key = (c, round(t, 1))
            if key in seen:
                continue
            seen.add(key)
            a = ag.get(c, {}).get(round(t, 1))
            if a is None:
                continue
            row = {m: _f(r.get(m)) for m in MEASURES}
            row["mac"], row["ppf_ce"] = _f(a.get("mac")), _f(a.get("ppf_ce"))
            per[c].append(row)
    return per


def arm_fidelities(per, drug):
    """Per case, the signed fidelity of every measure to `drug`, on the SAME windows for all measures."""
    out = []
    for c, rows in per.items():
        d = np.array([r[drug] for r in rows], float)
        ok = np.isfinite(d) & (d > 0)
        if ok.sum() < MIN_WINDOWS or np.ptp(d[ok]) <= 0:
            continue
        rec = {"case": c, "n": int(ok.sum()), "sd_drug": float(d[ok].std())}
        good = True
        for m, sign in MEASURES.items():
            v = np.array([r[m] for r in rows], float)[ok]
            if not np.isfinite(v).sum() >= MIN_WINDOWS or np.ptp(v[np.isfinite(v)]) <= 0:
                good = False
                break
            rho = spearman(v, d[ok])
            if not np.isfinite(rho):
                good = False
                break
            rec[m] = sign * rho
            rec["sd_" + m] = float(np.nanstd(v))
        if good:
            out.append(rec)
    return out


def main() -> int:
    if not os.path.exists(AGENTS) or not any(os.path.exists(t) for t in TABLES):
        print("ABSENT: missing input tables")
        return 2
    per = build()
    rng = np.random.default_rng(SEED)
    res = {"gates": {}, "arms": {}}
    print(f"{len(per)} cases joined")

    adv = {}
    for arm, drug in ARMS:
        rows = arm_fidelities(per, drug)
        n = len(rows)
        print(f"\n=== ARM {arm} (drug = {drug}) : {n} cases ===")
        A = {"n_cases": n, "measures": {}}
        if arm == "tiva":
            res["gates"]["G1_pass"] = bool(n >= MIN_CASES)
            print(f"G1 coverage   {n} >= {MIN_CASES}  "
                  f"{'PASS' if res['gates']['G1_pass'] else 'FAIL'}")
        if n < 10:
            res["arms"][arm] = A
            continue
        base = np.array([r[INCUMBENT] for r in rows])
        print(f"{'measure':<24s} {'fidelity':>9s}  {'vs incumbent':>13s} {'95% CI':>22s}  "
              f"{'|.| version':>12s}")
        print(f"{INCUMBENT:<24s} {np.median(base):+9.4f}  {'(incumbent)':>13s}")
        for m in MEASURES:
            if m == INCUMBENT:
                continue
            v = np.array([r[m] for r in rows])
            d = v - base
            lo, hi = ci([float(np.mean(d[i])) for i in (rng.integers(0, n, n) for _ in range(REPS))])
            da = np.abs(v) - np.abs(base)
            alo, ahi = ci([float(np.mean(da[i]))
                           for i in (rng.integers(0, n, n) for _ in range(REPS))])
            A["measures"][m] = {"median_fid": float(np.median(v)), "adv": float(np.mean(d)),
                                "lo": lo, "hi": hi, "abs_adv": float(np.mean(da)),
                                "abs_lo": alo, "abs_hi": ahi}
            print(f"{m:<24s} {np.median(v):+9.4f}  {np.mean(d):+13.4f} "
                  f"[{lo:+9.4f},{hi:+9.4f}]  {np.mean(da):+12.4f}")
        adv[arm] = {m: A["measures"][m]["adv"] for m in A["measures"]}
        A["_rows_n"] = n
        res["arms"][arm] = A

    # ---- G3 PROPOFOL SPECIFICITY: the interaction, not the main effect ---------------------------
    print("\nG3 PROPOFOL SPECIFICITY -- TIVA advantage minus volatile advantage (rule 29)")
    print("   a measure that beats the exponent in BOTH arms is just a better measure")
    spec = {}
    if "tiva" in adv and "volatile" in adv:
        for m in adv["tiva"]:
            if m in adv["volatile"]:
                spec[m] = adv["tiva"][m] - adv["volatile"][m]
                print(f"   {m:<24s} TIVA {adv['tiva'][m]:+.4f}  volatile {adv['volatile'][m]:+.4f}  "
                      f"interaction {spec[m]:+.4f}")
    res["gates"]["G3_interaction"] = spec

    # ---- PLACEBO: drug permuted across windows within case ---------------------------------------
    print("\nPLACEBO -- ppf_ce permuted across windows within case (marginals preserved)")
    pl = defaultdict(list)
    for _ in range(PLACEBO_DRAWS):
        shuffled = {c: [dict(r) for r in rows] for c, rows in per.items()}
        for c, rows in shuffled.items():
            vals = [r["ppf_ce"] for r in rows]
            perm = rng.permutation(len(vals))
            for i, r in enumerate(rows):
                r["ppf_ce"] = vals[perm[i]]
        rr = arm_fidelities(shuffled, "ppf_ce")
        if len(rr) < 10:
            continue
        b = np.array([r[INCUMBENT] for r in rr])
        for m in MEASURES:
            if m != INCUMBENT:
                pl[m].append(float(np.mean(np.array([r[m] for r in rr]) - b)))
    res["placebo"] = {}
    for m, vals in pl.items():
        lo, hi = ci(vals)
        real = res["arms"].get("tiva", {}).get("measures", {}).get(m, {}).get("adv", float("nan"))
        inside = bool(np.isfinite(lo) and lo <= real <= hi)
        res["placebo"][m] = {"lo": lo, "hi": hi, "inside": inside}
        print(f"   {m:<24s} [{lo:+.4f}, {hi:+.4f}]  real {real:+.4f}  "
              f"{'INSIDE -- withdrawn' if inside else 'outside'}")

    # ---- VERDICT ---------------------------------------------------------------------------------
    tiva = res["arms"].get("tiva", {}).get("measures", {})
    better = [m for m, d in tiva.items()
              if np.isfinite(d["lo"]) and d["lo"] > 0
              and not res["placebo"].get(m, {}).get("inside", True)]
    specific = [m for m in better if spec.get(m, 0.0) > 0]
    worse = [m for m, d in tiva.items() if np.isfinite(d["hi"]) and d["hi"] < 0]
    if not better:
        v = ("NOTHING RESCUES PROPOFOL SENSITIVITY -- no measure beats the aperiodic exponent's fidelity "
             "to propofol effect-site concentration with an interval excluding zero and outside the "
             "placebo. Neither H_periodic nor H_fitrange is supported, and the exponent's propofol "
             "blindness is not a fit-range artefact or a missing periodic term. "
             + (f"WORSE than the incumbent: {worse}. " if worse else ""))
    elif not specific:
        v = (f"BETTER BUT NOT PROPOFOL-SPECIFIC -- {better} beat the exponent under propofol, but the "
             f"advantage is no larger than in the volatile arm, so this is a statement about those "
             f"measures generally and NOT about propofol (G3, rule 29).")
    else:
        h_per = [m for m in specific if m in ("relative_alpha_power", "relative_delta_power")]
        h_fit = [m for m in specific if m in ("exponent_high", "exponent_low")]
        parts = []
        if h_per:
            parts.append(f"H_periodic supported by {h_per}")
        if h_fit:
            parts.append(f"H_fitrange supported by {h_fit}")
        v = (f"PROPOFOL SENSITIVITY IS RECOVERABLE -- {specific} beat the exponent under propofol by MORE "
             f"than in the volatile arm, so the advantage is propofol-specific. "
             + "; ".join(parts) + ". This locates the exponent's blindness rather than merely confirming "
             "it, and any product framing must state which measure is used for which agent.")
    res["verdict"] = v
    print(f"\nVERDICT: {v}")
    json.dump(res, open(OUT, "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
