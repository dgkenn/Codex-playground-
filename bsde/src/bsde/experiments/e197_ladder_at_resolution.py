#!/usr/bin/env python3
"""E197 — the same ladder, at a resolution that can tell the three placebo families apart.

REGISTERED BEFORE ANY DRAW AT THE HIGHER REPLICATE COUNT.

=========================================================================================================
WHY: E191's TWO FAMILIES DISAGREED BY ONE MONTE CARLO DRAW
=========================================================================================================
E191 measured, for each placebo family, the fraction of pure-noise AR(1) columns that beat their own
placebo distribution at a 5 % bar — a false-positive rate, at each rung of an autocorrelation ladder that
spans the real candidates' own measured lag-1 autocorrelation (0.678 to 0.955).

    rung             0.00    0.50    0.80    0.95    0.99
    circular shift   0.050   0.100   0.150   0.050   0.250     -> NO FAMILY USABLE
    IAAFT            0.050   0.050   0.100   0.050   0.200     -> USABLE, 10 of 11 licensed

**Those two verdicts are separated by a single draw.** At n = 20 the Wilson lower bound crosses the nominal
0.05 between 2 hits (0.028, passes) and 3 hits (0.052, fails). The families differ at rung 0.80 by exactly
that — 3/20 against 2/20. Rule 46: when a verdict's margin is the size of its Monte Carlo error, the binary
is a property of the RNG rather than of the data, and the repair is to raise the replicate count, which
changes no threshold, cohort or estimand.

**At n = 60 the gate flips between 6 hits (0.100, lower bound 0.046, passes) and 7 (0.117, lower bound
0.057, fails)** — a resolution of about 1.7 percentage points instead of 5.

=========================================================================================================
WHAT IS AND IS NOT CHANGED
=========================================================================================================
Unchanged: the cohort, the incumbent, the AR(1) ladder and its five rungs, the 5 % bar, the Wilson
interval, the "usable only if the lower bound does not exceed nominal" rule, the G4 decorrelation
requirement, and the span rule that a candidate is readable only if both rungs bracketing its own
autocorrelation are usable.

Changed: `N_REPS` 20 -> 60, and `N_SURR` 60 -> 50 so the cost stays bearable. Fifty placebo draws still
resolve the 5 % bar exactly (a fraction over 50 takes the value 0.04 and 0.06 either side of it, so a
column at the bar is decided, not rounded), and the quantity being estimated more precisely is the RATE
across columns, which is where the resolution was missing.

Added: a **third family**, the donor placebo (a real contiguous block of the same measure from a different
recording), so all three are measured on one ladder with one bar rather than compared across files.

Added: the **pooled rate over the four rungs at or below 0.95**, with its own Wilson interval. This is a
descriptive quantity and gates nothing; it exists because the per-rung gate discards information that the
question "is this family calibrated where the candidates live" can use.

=========================================================================================================
VERDICT — WRONG-DIRECTION CASES FIRST (rule 37)
=========================================================================================================
  (1) NOT INTERPRETABLE   the cohort or incumbent gate fails, or no family passes G3 aliveness.
  (2) NO FAMILY USABLE    no family holds nominal on the rungs bracketing the real candidates. Challenge C
                          then has no licensed way to ask this question on DOSE-I and E187's table stays
                          unlicensed permanently.
  (3) FAMILIES DISAGREE   at least one family is usable and at least one is not, with **non-overlapping**
                          Wilson intervals at the rung where they differ. Then the disagreement is real
                          and is itself the finding: these placebos are not interchangeable.
  (4) FAMILIES AGREE      the usable families' intervals overlap at every rung; the licensed candidate set
                          is whatever they jointly license.

**REGISTERED PREDICTION: (4), with all three families usable up to rho = 0.95 and none at 0.99**, and with
E191's apparent family difference at rung 0.80 disappearing — i.e. I predict E191's two verdicts were the
same measurement seen at insufficient resolution. The concrete numbers I expect are per-rung rates between
0.03 and 0.12 for every family below rho = 0.95. **If (3) comes back with non-overlapping intervals, the
choice of placebo family is a scientific decision rather than a technical one, and every result in this
programme that used one would need restating with that caveat.**

    python bsde/src/bsde/experiments/e197_ladder_at_resolution.py [--family iaaft|circular_shift|donor]
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, HERE)

from e150_challenge_c_negatives_rederived import build                               # noqa: E402
from e180_moaas_label_placebo import E150_ADDS, baseline_perf                         # noqa: E402
from e190_circular_shift_placebo import absolute_ac, positive_control                 # noqa: E402
from e190_circular_shift_placebo import surrogate_column as shift_column              # noqa: E402
from e191_functional_surrogate_calibration import (LADDER, ar1_column,                # noqa: E402
                                                   fraction_at_or_below, iaaft_column)
from e194_donor_column_placebo import _donor                                          # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
E150_JSON = os.path.join(RESULTS, "e150_challenge_c_rederived.json")
SEED = 20260801

N_REPS = 60        # 20 -> 60: the gate now flips between 6 and 7 hits, not 2 and 3
N_SURR = 50        # 60 -> 50 to keep the cost bearable; still resolves the 5 % bar exactly
CORR_MAX = 0.30
ALPHA = 0.05
NOMINAL = 0.05
POOL_MAX_RUNG = 0.95

FAMILIES = {"iaaft": iaaft_column, "circular_shift": shift_column, "donor": _donor}

try:
    _e150 = json.load(open(E150_JSON))
    N_RECORDINGS, N_WINDOWS = int(_e150["n_recordings"]), int(_e150["n_windows"])
except Exception:                                                              # noqa: BLE001
    N_RECORDINGS, N_WINDOWS = -1, -1


def wilson(hits, n):
    if not n:
        return float("nan"), float("nan")
    z = 1.959963985
    c = (hits + z * z / 2) / (n + z * z)
    h = z * np.sqrt(hits * (n - hits) / n + z * z / 4) / (n + z * z)
    return max(0.0, c - h), min(1.0, c + h)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", default=None, choices=sorted(FAMILIES))
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    fams = {a.family: FAMILIES[a.family]} if a.family else dict(FAMILIES)
    out_path = a.out or os.path.join(RESULTS, "e197_ladder_at_resolution.json")

    print(f"E197 — the ladder at n = {N_REPS} per rung; gate flips between "
          f"{int(np.ceil(0.05 * N_REPS)) + 1} and "
          f"{int(np.ceil(0.05 * N_REPS)) + 2} hits, not 2 and 3")
    y, subj, base, cand, cands, n_rec = build()
    res = {"experiment": "E197", "n_recordings": int(n_rec), "n_windows": int(len(y)),
           "ladder": list(LADDER), "n_reps": N_REPS, "n_surrogates": N_SURR,
           "alpha": ALPHA, "nominal": NOMINAL, "families": {}}

    g1 = bool(n_rec == N_RECORDINGS and len(y) == N_WINDOWS)
    rho_b = baseline_perf(base, y, subj, SEED)
    g2 = bool(np.isfinite(rho_b) and rho_b > 0.20)
    print(f"G1 REBUILD {n_rec}/{len(y)} vs {N_RECORDINGS}/{N_WINDOWS}  {'PASS' if g1 else 'FAIL'}   "
          f"G2 INCUMBENT rho {rho_b:+.4f}  {'PASS' if g2 else 'FAIL'}")
    res["g1_rebuild"], res["g2_incumbent_rho"] = g1, float(rho_b)
    if not (g1 and g2):
        res["verdict"] = "NOT INTERPRETABLE"
        json.dump(res, open(out_path, "w"), indent=2)
        return 1

    ac = {}
    for name in E150_ADDS:
        x = cand.get(name)
        if x is not None:
            a1, a9 = absolute_ac(x, subj)
            ac[name] = {"ac1": a1, "ac9": a9}
    res["candidate_autocorrelation"] = ac

    for fam_name, fam in fams.items():
        print(f"\n{'=' * 100}\nFAMILY: {fam_name}")
        pc = positive_control(y, subj, np.random.default_rng(SEED + 888))
        real, frac, rho_s = fraction_at_or_below(pc, base, y, subj, fam, 200, 41000)
        alive = bool(np.isfinite(frac) and frac <= ALPHA and np.isfinite(rho_s)
                     and rho_s < CORR_MAX)
        print(f"G3 ALIVENESS  positive control real {real:+.5f}, frac {frac:.4f}, "
              f"placebo rho {rho_s:.3f}   {'PASS' if alive else '*** FAIL'}")
        fres = {"aliveness": {"real": real, "frac": frac, "rho": rho_s, "pass": alive}, "rungs": {}}

        print(f"\n   {'rung':>6s} {'n':>4s} {'hits':>5s} {'FP rate':>9s} {'[Wilson 95%]':>18s} "
              f"{'rho':>7s}  usable")
        pool_hits = pool_n = 0
        for rho_t in LADDER:
            fr, rhos = [], []
            for r in range(N_REPS):
                x = ar1_column(subj, rho_t, np.random.default_rng(
                    SEED + 60000 + int(rho_t * 1000) * 1000 + r))
                _re, f, rs = fraction_at_or_below(
                    x, base, y, subj, fam, N_SURR,
                    70000 + int(rho_t * 1000) * 1000 + r * 7)
                if np.isfinite(f):
                    fr.append(f)
                if np.isfinite(rs):
                    rhos.append(rs)
            fr = np.asarray(fr)
            n = int(fr.size)
            hits = int((fr <= ALPHA).sum()) if n else 0
            lo, hi = wilson(hits, n)
            r_ = float(np.mean(rhos)) if rhos else float("nan")
            ok_rho = bool(np.isfinite(r_) and r_ < CORR_MAX)
            usable = bool(ok_rho and np.isfinite(lo) and lo <= NOMINAL)
            fres["rungs"][f"{rho_t}"] = {"n": n, "hits": hits,
                                         "fp_rate": hits / n if n else float("nan"),
                                         "ci": [lo, hi], "rho": r_, "g4_destroys": ok_rho,
                                         "usable": usable}
            if rho_t <= POOL_MAX_RUNG:
                pool_hits += hits
                pool_n += n
            print(f"   {rho_t:>6.2f} {n:>4d} {hits:>5d} {hits / max(n, 1):>9.3f} "
                  f"[{lo:>7.3f}, {hi:>7.3f}] {r_:>7.3f}  "
                  f"{'yes' if usable else ('NO (G4)' if not ok_rho else 'NO')}", flush=True)
        plo, phi = wilson(pool_hits, pool_n)
        fres["pooled_below_095"] = {"hits": pool_hits, "n": pool_n,
                                    "rate": pool_hits / pool_n if pool_n else float("nan"),
                                    "ci": [plo, phi]}
        print(f"   POOLED rho <= {POOL_MAX_RUNG}: {pool_hits}/{pool_n} = "
              f"{pool_hits / max(pool_n, 1):.3f} [{plo:.3f}, {phi:.3f}]   (descriptive, gates nothing)")

        def brackets(a1):
            below = [r for r in LADDER if r <= a1]
            above = [r for r in LADDER if r >= a1]
            if not np.isfinite(a1) or not below or not above:
                return False
            return (fres["rungs"][f"{max(below)}"]["usable"]
                    and fres["rungs"][f"{min(above)}"]["usable"])

        fres["licensed"] = [n for n, v in ac.items() if brackets(v["ac1"])] if alive else []
        print(f"   licensed candidates: {fres['licensed'] or 'NONE'}")
        res["families"][fam_name] = fres

    if len(res["families"]) > 1:
        usable_f = [k for k, v in res["families"].items() if v["licensed"]]
        unusable = [k for k in res["families"] if k not in usable_f]
        disagree = []
        for rho_t in LADDER:
            cis = {k: v["rungs"][f"{rho_t}"]["ci"] for k, v in res["families"].items()}
            for i, (ka, ca) in enumerate(cis.items()):
                for kb, cb in list(cis.items())[i + 1:]:
                    if np.isfinite(ca[1]) and np.isfinite(cb[0]) and (ca[1] < cb[0] or cb[1] < ca[0]):
                        disagree.append((rho_t, ka, kb))
        print("\n" + "=" * 100)
        if not any(v["aliveness"]["pass"] for v in res["families"].values()):
            v, why = "NOT INTERPRETABLE", "no family lets the positive control survive"
        elif not usable_f:
            v, why = "NO FAMILY USABLE", (
                "no family holds nominal on the rungs bracketing the real candidates, so E187's table "
                "stays unlicensed permanently and Challenge C has no licensed way to ask this on DOSE-I")
        elif unusable and disagree:
            v, why = "FAMILIES DISAGREE", (
                f"usable: {usable_f}; not usable: {unusable}; with NON-OVERLAPPING Wilson intervals at "
                f"{disagree}. The choice of placebo family is a scientific decision, not a technical one")
        elif unusable:
            v, why = "FAMILIES AGREE", (
                f"usable: {usable_f}; not usable: {unusable} — but no pair of families has "
                "non-overlapping intervals at any rung, so the split is a threshold artefact and not a "
                "measured difference between the placebos")
        else:
            v, why = "FAMILIES AGREE", (
                f"all of {list(res['families'])} are usable; jointly licensed candidates: "
                f"{sorted(set.intersection(*(set(v['licensed']) for v in res['families'].values())))}")
        res["verdict"], res["why"] = v, why
        print(f"VERDICT: {v}\n  {why}")
        print("=" * 100)

    os.makedirs(RESULTS, exist_ok=True)
    json.dump(res, open(out_path, "w"), indent=2)
    print(f"\nwrote -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
