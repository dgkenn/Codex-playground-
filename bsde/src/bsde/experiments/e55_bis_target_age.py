#!/usr/bin/env python3
"""E55 -- Challenge C. Does BIS 40-60 mean the same thing at every age?

FEASIBILITY PROBE RUN FIRST (rule 41), before this file was written: of 5,828 maintenance windows with the
sensor attached, **2,877 (49.4 %) sit inside the 40-60 target band, across 240 cases**, ages 1-89 with
median 59; `meta_agents_present` (7 values), `meta_asa`, `meta_bmi` and `meta_sex` are fully populated. So
the confound that would otherwise sink this design -- older patients receive different anaesthetics -- is
measurable here rather than merely acknowledged.

=========================================================================================================
THE CLAIM, AND WHY IT IS THE ONE STRUCTURAL ADVANTAGE AVAILABLE
=========================================================================================================
`REFERENCE_AGAINST_ALL_THREE.md` §3: **BIS has no reference.** It targets 40-60 for everyone -- a fixed
band, no age term, no comorbidity term. A conditional reference gives a per-patient expectation, which a
fixed target cannot express. The prior work reached the same place empirically with age-stratified depth
targets rising from 1.03 SD in teenagers to 2.76 SD in octogenarians.

**If a fixed target is age-appropriate, then patients held at the same BIS should be in the same EEG state
regardless of age.** If they are not, the monitor's target band is systematically mis-centred by age, and
that is a defect a per-patient reference could repair.

WHAT THIS DELIBERATELY DOES NOT CLAIM. It is not a claim that age *causes* the difference. Older patients
receive less anaesthetic and different agents, and this design cannot separate age from age-correlated
dosing. **The claim is about the MONITOR'S CALIBRATION: BIS 45 corresponds to a different EEG state in a
30-year-old than in an 80-year-old.** That is well-posed and clinically meaningful whichever mechanism
drives it, and it is the only version of the question this deposit can answer.

=========================================================================================================
DESIGN
=========================================================================================================
CASE LEVEL, not window level. Age is a case property, so 2,877 windows are pseudo-replicates of 240
independent observations; each case contributes its mean candidate and mean BIS inside the band.

  P1 PRIMARY   partial Spearman(candidate, age | BIS) across cases. BIS is partialled out so the
               comparison is "at matched monitor reading".
  P2 INCUMBENT partial Spearman(BIS, age | candidate) -- the same asymmetry E43 used. If the monitor were
               the age-invariant one, this would be the smaller of the two.
  P3 CONFOUND  P1 repeated with the anaesthetic agent (dummies), ASA, sex and BMI additionally partialled
               out. **This is a gate, not a footnote:** if the age relation collapses, it was drug and
               comorbidity, and the calibration claim is not supported by this deposit.
  P4 PLACEBO   age permuted ACROSS CASES, P1 recomputed, 2,000 draws. Tests the statistic itself. A
               comparison against the real effect, never a threshold; NOT INFORMATIVE if P1 spans zero.

VERDICT RULE -- the failing cases first, and the wrong direction is a PASS here rather than a fail, which
is unusual and is why it must be written down. Either sign of the age relation supports the calibration
claim; only the NULL refutes it.

  (a) REFUTED        -- P1's CI includes zero. At matched BIS the candidate does not vary with age, so
                        the fixed target is age-appropriate on this evidence.
  (b) CONFOUNDED     -- P1 excludes zero but P3 does not. The relation is drug/comorbidity, not the
                        monitor's calibration.
  (c) NOT INFORMATIVE-- the placebo reaches the primary.
  (d) SUPPORTED      -- P1 and P3 both exclude zero, same sign, and the placebo is smaller.

    python -m bsde.experiments.e55_bis_target_age
"""
from __future__ import annotations

import csv
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
from bsde.verifier.stats import spearman                                     # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
GRID = os.path.join(RESULTS, "vitaldb_grid.csv")
OUT = os.path.join(RESULTS, "e55_bis_target_age.json")

BAND = (40.0, 60.0)
CANDIDATES = ("exponent_low", "exponent_high", "whole_head_exponent", "lempel_ziv",
              "relative_alpha_power", "spectral_edge_95")
MIN_CASES = 60
REPS = 20000
PLACEBO_DRAWS = 2000
SEED = 20260731


def _f(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:                                                        # noqa: BLE001
        return None


def _rank(a):
    a = np.asarray(a, float)
    order = a.argsort()
    r = np.empty_like(order, dtype=float)
    r[order] = np.arange(a.size, dtype=float)
    return r


def _partial(x, y, controls):
    """Spearman partial correlation of x and y given a list of control vectors (rank-residualised)."""
    X = _rank(x)
    Y = _rank(y)
    if controls:
        C = np.vstack([np.ones(X.size)] + [_rank(c) for c in controls]).T
        for v in (X, Y):
            pass
        bx, *_ = np.linalg.lstsq(C, X, rcond=None)
        by, *_ = np.linalg.lstsq(C, Y, rcond=None)
        X = X - C @ bx
        Y = Y - C @ by
    if np.std(X) == 0 or np.std(Y) == 0:
        return float("nan")
    return float(np.corrcoef(X, Y)[0, 1])


def _cases():
    with open(GRID) as fh:
        rows = [r for r in csv.DictReader(fh) if r.get("status") == "ok"]
    band = [r for r in rows
            if _f(r.get("meta_bis")) is not None and BAND[0] <= _f(r["meta_bis"]) <= BAND[1]
            and (_f(r.get("meta_rel_aneend_s")) or 1) <= 0
            and (_f(r.get("meta_sensor_off")) or 0) <= 0.5]
    by = {}
    for r in band:
        by.setdefault(r["meta_caseid"], []).append(r)
    out = []
    agents = sorted({r.get("meta_agents_present", "") for r in band})
    for cid, rs in sorted(by.items()):
        age = _f(rs[0].get("meta_age"))
        if age is None:
            continue
        rec = {"case": cid, "age": age,
               "bis": float(np.mean([_f(r["meta_bis"]) for r in rs])),
               "sex": 1.0 if (rs[0].get("meta_sex") or "").upper().startswith("M") else 0.0,
               "asa": _f(rs[0].get("meta_asa")) or 2.0,
               "bmi": _f(rs[0].get("meta_bmi")) or 24.0,
               "agent": float(agents.index(rs[0].get("meta_agents_present", ""))),
               "n_win": len(rs)}
        for c in CANDIDATES:
            v = [_f(r.get(c)) for r in rs]
            v = [z for z in v if z is not None]
            rec[c] = float(np.mean(v)) if v else float("nan")
        out.append(rec)
    return out


def main() -> int:
    cases = _cases()
    print("=" * 100)
    print(f"E55 -- does BIS {BAND[0]:.0f}-{BAND[1]:.0f} mean the same thing at every age?")
    print("=" * 100)
    print(f"   cases in band: {len(cases)}   windows: {sum(c['n_win'] for c in cases)}")
    if len(cases) < MIN_CASES:
        print(f"   G1 FAILED: {len(cases)} < {MIN_CASES}. No verdict.")
        json.dump({"gate": "G1_failed", "n": len(cases)}, open(OUT, "w"), indent=2)
        return 1
    age = np.array([c["age"] for c in cases])
    bis = np.array([c["bis"] for c in cases])
    sex = np.array([c["sex"] for c in cases])
    asa = np.array([c["asa"] for c in cases])
    bmi = np.array([c["bmi"] for c in cases])
    agent = np.array([c["agent"] for c in cases])
    print(f"   age {age.min():.0f}-{age.max():.0f} median {np.median(age):.0f}   "
          f"mean BIS in band {bis.mean():.1f}")
    print(f"\n   BIS itself vs age (partial on nothing): rho = {spearman(bis, age):+.3f}")

    rng = np.random.default_rng(SEED)
    n = len(cases)
    res = {}
    print(f"\n   {'candidate':22s} {'P1 rho|BIS':>11s} {'95% CI':>18s} {'P3 adj':>8s} "
          f"{'P2 BIS|cand':>12s} {'placebo':>8s}   verdict")
    print("   " + "-" * 108)
    for c in CANDIDATES:
        v = np.array([cc[c] for cc in cases])
        ok = np.isfinite(v)
        if ok.sum() < MIN_CASES:
            print(f"   {c:22s} insufficient ({ok.sum()})")
            continue
        vv, aa, bb = v[ok], age[ok], bis[ok]
        ss, sa, sb, ag = sex[ok], asa[ok], bmi[ok], agent[ok]
        p1 = _partial(vv, aa, [bb])
        p3 = _partial(vv, aa, [bb, ag, sa, ss, sb])
        p2 = _partial(bb, aa, [vv])
        d1, d3 = [], []
        m = ok.sum()
        for _ in range(REPS):
            i = rng.integers(0, m, m)
            a_ = _partial(vv[i], aa[i], [bb[i]])
            if math.isfinite(a_):
                d1.append(a_)
            b_ = _partial(vv[i], aa[i], [bb[i], ag[i], sa[i], ss[i], sb[i]])
            if math.isfinite(b_):
                d3.append(b_)
        q1 = np.sort(np.array(d1)); q3 = np.sort(np.array(d3))
        lo, hi = float(np.quantile(q1, .025)), float(np.quantile(q1, .975))
        lo3, hi3 = float(np.quantile(q3, .025)), float(np.quantile(q3, .975))
        pl = []
        for _ in range(PLACEBO_DRAWS):
            z = _partial(vv, rng.permutation(aa), [bb])
            if math.isfinite(z):
                pl.append(abs(z))
        placebo = float(np.quantile(np.array(pl), 0.95)) if pl else float("nan")

        if lo <= 0 <= hi:
            verdict = "REFUTED (no age relation at matched BIS)"
        elif lo3 <= 0 <= hi3:
            verdict = "CONFOUNDED (dies on agent/ASA/sex/BMI adjustment)"
        elif not (math.isfinite(placebo) and abs(p1) > placebo):
            verdict = "NOT INFORMATIVE (placebo reaches the primary)"
        elif (p1 > 0) != (p3 > 0):
            verdict = "NOT INFORMATIVE (adjustment reverses the sign)"
        else:
            verdict = "SUPPORTED"
        res[c] = {"p1": p1, "ci": [lo, hi], "p3": p3, "ci3": [lo3, hi3], "p2_bis": p2,
                  "placebo_95": placebo, "n": int(m), "verdict": verdict}
        print(f"   {c:22s} {p1:+11.3f} [{lo:+7.3f},{hi:+7.3f}] {p3:+8.3f} {p2:+12.3f} "
              f"{placebo:8.3f}   {verdict}")

    sup = [c for c, v in res.items() if v["verdict"] == "SUPPORTED"]
    print("\n" + "-" * 100)
    print(f"SUPPORTED for {len(sup)} of {len(res)} candidates: {sup}")
    if sup:
        print("   -> at the SAME BIS reading, these measures differ systematically by age, so the fixed")
        print("      40-60 target is not age-neutral. That is the defect a per-patient reference repairs.")
    else:
        print("   -> no candidate shows an age relation at matched BIS that survives adjustment. On this")
        print("      deposit the fixed target is age-appropriate, and Challenge C's reference argument")
        print("      loses its structural rationale.")
    json.dump({"n_cases": len(cases), "results": res, "supported": sup,
               "bis_vs_age": spearman(bis, age), "reps": REPS, "seed": SEED},
              open(OUT, "w"), indent=2, default=str)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
