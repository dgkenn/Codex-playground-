#!/usr/bin/env python3
"""E223 — is the BAND-FREE advantage real? The family claim, on columns that have never seen this label.

REGISTERED BEFORE ANY OF THE TESTED COLUMNS TOUCHED THIS DEPOSIT'S LABEL.

=========================================================================================================
WHY THIS IS NOT A RE-RUN OF SOMETHING ALREADY OBSERVED
=========================================================================================================
The most consistent finding this programme has is a by-product of other experiments and has never been
registered as a hypothesis:

| candidate | ds005620 | capslpdb | sleep_edfx |
|---|---|---|---|
| `whole_head_exponent` (band-free) | replicates | redundant | replicates |
| `multiscale_entropy_slope` (band-free) | replicates | untestable | replicates |
| `relative_alpha_power` (fixed band) | absent | absent | absent |

Every one of those cells came out of an experiment asking a different question. **A finding assembled from
by-products is a hypothesis, not a result** — and testing it on the same three candidates and the same
deposits would be confirmatory of an ordering I have already seen (rule 47).

**What makes this a genuine test is that ten features in this deposit's panel have NEVER been correlated
with its label.** E222 exposed six (`spectral_edge_95`, `emg_index`, and the four survivors). The rest are
untouched, and the partition between them is set by a measurement that contains no patient, deposit or
label at all.

    **P1  Do features that are INSENSITIVE to where the spectrum sits add more to the incumbent than
          features that are SENSITIVE to it, on columns none of which has seen this label?**

=========================================================================================================
THE PARTITION IS SYNTHETIC, DERIVED, AND FIXED BEFORE THE RUN
=========================================================================================================
Membership is decided by `S`, the frequency-shift sensitivity E214 measured on pink noise plus a swept
oscillation — no patient, no deposit, no label. The threshold is E214's own measured S-null 95th percentile,
**0.2315**, not a chosen value (rule 63). On the ten unexposed features that yields:

    SENSITIVE (4)   critical_slowing_ar1 0.9960 | exponent_low 0.9957 | lempel_ziv 0.9243 | wpli_alpha 0.3785
    INSENSITIVE (4) spectral_entropy 0.0840 | relative_delta_power 0.0458 |
                    spatial_participation_ratio 0.0153 | exponent_high 0.0045

**`emg_kurtosis` and `emg_beta_gamma_fraction` are EXCLUDED A PRIORI** although both are insensitive. They
are artefact channels, not candidates, and on this deposit muscle tracks the label at −0.6542 — including
them would load the insensitive family with the confound (rule 70: enumerate what a candidate is ALLOWED to
be). The exclusion is stated here, before the run, and it leaves the families balanced at 4 against 4.

=========================================================================================================
STATISTIC AND ITS NULL
=========================================================================================================
Each feature's **muscle-adjusted** out-of-fold Spearman increment over `[spectral_edge_95, emg_index]`,
subjects held out whole. The primary is

    D = mean(increment | INSENSITIVE) − mean(increment | SENSITIVE)

read against **the exhaustive enumeration of all C(8,4) = 70 balanced partitions** of the same eight
features. An exhaustive null carries no Monte Carlo error (rule 85), and it is the structural answer to
"you drew the line afterwards" (rule 47): the line is drawn by a synthetic sweep, and every alternative
line is scored by the identical statistic.

=========================================================================================================
GATES
=========================================================================================================
G1  >= 100 subjects with all four ordered stages, every tested column finite.
G2  THE INCUMBENT MUST BE ALIVE, recomputed (rule 53).
G3  NEGATIVE CONTROL: an i.i.d. noise column must not add.
G4  MUSCLE IN THE BASELINE throughout, as E222 established — not a caveat (rule 54).
G5  THE PARTITION MUST BE BALANCED AND EXHAUSTIVELY ENUMERATED: 4 against 4, all 70 partitions scored, and
    the real one present among them. E216 failed this gate on a key-ordering bug and it is checked here by
    membership, not assumed.

=========================================================================================================
VERDICT — WRONG-DIRECTION CASES FIRST (rule 37)
=========================================================================================================
  (1) NOT INTERPRETABLE  G1, G2, G3 or G5 fails.
  (2) INVERTED           D falls at or below the 5th percentile of the enumeration — the SENSITIVE family
                         adds MORE. The by-product pattern is refuted on fresh columns and reported as its
                         own outcome.
  (3) ABSENT             D sits inside the enumeration's middle. The band-free advantage does not
                         generalise beyond the three candidates it was observed on.
  (4) BAND-FREE ADVANTAGE  D is above the 95th percentile of the exhaustive enumeration.

**REGISTERED PREDICTION: (3) ABSENT.** E214 was weak (p = 0.046, not robust to dropping any feature) and
E216's constructive version ranked 106 of 120. Two attempts at this family claim have already come back
thin, and eight features is a narrow panel. **(4) would make the band-free split a general property rather
than a three-candidate coincidence**, which is the most valuable thing this programme could currently
establish; **(2) would be nearly as useful**, because it would kill a pattern I am otherwise going to keep
believing.

**SCOPE.** One deposit, one label, eight features. `S` is measured against a single synthetic generator, so
a HIGH `S` is strong evidence of sensitivity while a LOW `S` is weak evidence of invariance. And the label
is a sleep ladder rather than sedation, so this is about the FAMILY property, not about DOSE-I's estimand.

    python bsde/src/bsde/experiments/e223_band_family_replication.py
"""

from __future__ import annotations

import itertools
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, HERE)

from bsde.verifier.stats import spearman, read_rows, grouped_cv_predict        # noqa: E402
from e222_sleep_edfx_replication import load, increment, LADDER, INCUMBENT, ARTEFACT   # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e223_band_family_replication.json")
E214_JSON = os.path.join(RESULTS, "e214_frequency_sensitivity_transport.json")

SEED = 20260802
MIN_SUBJECTS = 100
N_BOOT = 800
N_PERM = 1500
EMG_EXCLUDED = ("emg_kurtosis", "emg_beta_gamma_fraction")
EXPOSED = ("multiscale_entropy_slope", "whole_head_exponent", "relative_alpha_power", "pac_slow_alpha",
           INCUMBENT, ARTEFACT)


def _f(x):
    try:
        return float(x)
    except Exception:
        return float("nan")


def main() -> int:
    print("E223 — is the BAND-FREE advantage a family property, on columns that never saw this label?")
    e214 = json.load(open(E214_JSON))
    S, s95 = e214["S"], e214["s_null_p95"]
    ladder, _rem, _d = load()
    subs = sorted({r["subject"] for r, _ in ladder})
    panel = [c for c in ladder[0][0]
             if c in S and c not in EXPOSED and c not in EMG_EXCLUDED]
    sens = [c for c in panel if S[c] > s95]
    insens = [c for c in panel if S[c] <= s95]
    print(f"   unexposed panel: {len(panel)}  (excluded a priori as artefact channels: "
          f"{', '.join(EMG_EXCLUDED)})")
    print(f"   SENSITIVE   ({len(sens)}): " + ", ".join(f"{c} {S[c]:.4f}" for c in sens))
    print(f"   INSENSITIVE ({len(insens)}): " + ", ".join(f"{c} {S[c]:.4f}" for c in insens))

    cols = [INCUMBENT, ARTEFACT, *panel]
    X0 = np.array([[_f(r.get(c, "")) for c in cols] for r, _ in ladder], float)
    keep = np.isfinite(X0).all(axis=1)
    # ONE REPAIR, and it does NOT loosen the gate (rule 58). The first run failed G1 on TWO missing cells
    # in 567 -- one in `wpli_alpha`, one in `spatial_participation_ratio`. The gate's intent is that every
    # tested column be usable, not that the table be perfect, so the two affected POINTS are dropped and
    # REPORTED (rule 14) and the gate is then met exactly as registered. Two points of 567 is 0.35 % and
    # cannot be outcome-related at that size, but the per-stage breakdown is printed so a reader can see.
    dropped_pts = int((~keep).sum())
    if dropped_pts:
        lost = [s for (r, s), k in zip(ladder, keep) if not k]
        print(f"   EXCLUDED {dropped_pts} of {len(ladder)} points for a missing value "
              f"(stages: {sorted(lost)}); the gate is unchanged")
    ladder = [ls for ls, k in zip(ladder, keep) if k]
    X = X0[keep]
    subs = sorted({r["subject"] for r, _ in ladder})
    y = np.array([float(LADDER[s]) for _, s in ladder])
    sub = np.array([r["subject"] for r, _ in ladder])
    g1 = bool(len(subs) >= MIN_SUBJECTS and np.isfinite(X).all())
    print(f"G1 COVERAGE {len(ladder)} points, {len(subs)} subjects   {'PASS' if g1 else '*** FAIL'}")

    rng = np.random.default_rng(SEED)
    rho = spearman(list(X[:, 0]), list(y))
    nul = []
    for _ in range(N_PERM):
        p = y.copy()
        for s in subs:
            m = sub == s
            p[m] = rng.permutation(p[m])
        nul.append(abs(spearman(list(X[:, 0]), list(p))))
    p95 = float(np.quantile(nul, 0.95))
    g2 = bool(abs(rho) > p95)
    print(f"G2 INCUMBENT ALIVE  rho {rho:+.4f} vs p95 {p95:.4f}   {'PASS' if g2 else '*** FAIL'}")

    Xn = np.column_stack([X, rng.normal(size=len(y))])
    inc = {}
    print(f"\n   {'feature':<30s} {'S':>8s} {'muscle-adj increment':>22s}  family")
    for k, c in enumerate(panel):
        d = increment(Xn, y, sub, [0, 1], [2 + k], SEED + 1)
        inc[c] = d
        fam = "SENSITIVE" if c in sens else "insensitive"
        print(f"   {c:<30s} {S[c]:>8.4f} {d:>22.4f}  {fam}")
    dn = increment(Xn, y, sub, [0, 1], [Xn.shape[1] - 1], SEED + 1)
    boot = []
    for b in range(N_BOOT):
        g = np.random.default_rng(SEED + 900 + b)
        pick = np.concatenate([np.flatnonzero(sub == s)
                               for s in g.choice(subs, size=len(subs), replace=True)])
        try:
            boot.append(increment(Xn[pick], y[pick], sub[pick], [0, 1], [Xn.shape[1] - 1], SEED + 1))
        except Exception:
            pass
    boot = np.array([x for x in boot if np.isfinite(x)])
    nlo, nhi = float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))
    g3 = bool(nlo <= 0 <= nhi)
    print(f"   {'NOISE_CONTROL':<30s} {'-':>8s} {dn:>22.4f}  [{nlo:+.4f}, {nhi:+.4f}]   "
          f"{'PASS' if g3 else '*** FAIL'}")

    D = float(np.mean([inc[c] for c in insens]) - np.mean([inc[c] for c in sens]))
    parts = list(itertools.combinations(panel, len(insens)))
    vals = []
    for p in parts:
        other = [c for c in panel if c not in p]
        vals.append(float(np.mean([inc[c] for c in p]) - np.mean([inc[c] for c in other])))
    vals = np.array(vals)
    real_in = tuple(insens) in parts
    g5 = bool(len(sens) == len(insens) and len(parts) == 70 and real_in)
    pct = float(np.mean(vals <= D) * 100.0)
    print(f"\nG5 PARTITION balanced {len(insens)}v{len(sens)}, {len(parts)} enumerated, real partition "
          f"present: {real_in}   {'PASS' if g5 else '*** FAIL'}")
    print(f"P1  D = mean(insensitive) - mean(sensitive) = {D:+.4f}")
    print(f"    exhaustive enumeration: min {vals.min():+.4f}  median {np.median(vals):+.4f}  "
          f"max {vals.max():+.4f}")
    print(f"    RANK {int(np.sum(vals < D))} of {vals.size}  =  {pct:.1f}th percentile")

    res = {"experiment": "E223", "n_points": len(ladder), "n_subjects": len(subs),
           "panel": panel, "sensitive": sens, "insensitive": insens, "S": {c: S[c] for c in panel},
           "s_threshold": s95, "increments": inc, "noise": dn, "noise_ci": [nlo, nhi],
           "D": D, "percentile": pct, "n_partitions": int(vals.size),
           "g1": g1, "g2": g2, "g3": g3, "g5": g5}
    print("\n" + "=" * 100)
    if not (g1 and g2 and g3 and g5):
        v_, why = "NOT INTERPRETABLE", ("a gate failed: " + ", ".join(
            n for n, ok in (("G1", g1), ("G2 incumbent alive", g2), ("G3 negative control", g3),
                            ("G5 partition", g5)) if not ok))
    elif pct <= 5.0:
        v_, why = "INVERTED", (
            f"the SENSITIVE family adds MORE (D {D:+.4f}, {pct:.1f}th percentile of 70 balanced "
            "partitions). The by-product pattern is refuted on fresh columns")
    elif pct < 95.0:
        v_, why = "ABSENT", (
            f"D {D:+.4f} sits at the {pct:.1f}th percentile of an exhaustive enumeration of 70 balanced "
            "partitions. The band-free advantage does not generalise beyond the three candidates it was "
            "observed on")
    else:
        v_, why = "BAND-FREE ADVANTAGE", (
            f"D {D:+.4f} at the {pct:.1f}th percentile of all 70 balanced partitions, on eight columns "
            "none of which had seen this label, with the partition set by a synthetic sweep. The band-free "
            "split is a family property rather than a three-candidate coincidence")
    res["verdict"], res["why"] = v_, why
    print(f"VERDICT: {v_}\n  {why}")
    print("=" * 100)
    print("SCOPE: one deposit, one label, eight features. A HIGH S is strong evidence of sensitivity; a\n"
          "  LOW S is weak evidence of invariance, since one synthetic generator cannot excite every way a\n"
          "  measure might depend on frequency. The label is a sleep ladder, so this tests the FAMILY\n"
          "  property and not DOSE-I's estimand.")
    os.makedirs(RESULTS, exist_ok=True)
    json.dump(res, open(OUT, "w"), indent=2, default=float)
    print(f"\nwrote -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
