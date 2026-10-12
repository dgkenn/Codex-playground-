#!/usr/bin/env python3
"""E213 — is Challenge A's `relative_alpha_power` inversion a BAND-PLACEMENT artefact?

REGISTERED BEFORE THE PRIMARY STATISTIC HAS BEEN COMPUTED IN ANY FORM.

=========================================================================================================
THE STANDING FINDING, AND WHY IT IS SUSPECT
=========================================================================================================
`relative_alpha_power` is one of the two features whose deep-versus-light relationship **inverts** between
propofol and sevoflurane, and it is separately the one Challenge C survivor that **fails to replicate** on
ds005620 (E209: +0.0978 [-0.0405, +0.2334] against two others that clear). One feature failing in two
different challenges for two apparently unrelated reasons is worth one cheap mechanical explanation before
any biological one.

The measure is **power in a FIXED 8-13 Hz window divided by power in 1-45 Hz.** It is not a measure of the
alpha oscillation; it is a measure of how much of that oscillation happens to fall inside a fixed box.

Three facts, all measured before this design and reported here as its premise:

  * `alpha_peak_hz` in this deposit is the raw-PSD maximum **inside 8-13 Hz**, so it structurally
    **cannot report a peak below 8 Hz** and pins at the floor instead. Measured over 6,437 finite windows:
    minimum exactly 8.000, maximum exactly 13.000, nothing outside. This is catalogue rule 62's failure in
    a new place — an estimator has no resolution outside the range it was built over.
  * At BIS < 40, **28.74 %** of volatile-agent windows sit exactly at the 8.0 Hz floor against **8.91 %** of
    propofol windows, a 3.2-fold excess. Every peak that has actually moved below 8 Hz is recorded as 8.0,
    so the propofol-minus-sevoflurane peak separation at depth is a **LOWER BOUND**, not an estimate.
  * At case level, over the 115 clean single-agent cases E186 defines: propofol's deep alpha peak has a
    median of 10.000 Hz with 4.5 % at the floor; sevoflurane's has a median of 8.500 Hz with **39.4 %** at
    the floor.

A peak sitting at or below the band's lower edge loses its lower skirt into theta, so a fixed 8-13 Hz
window **under-counts sevoflurane's alpha at depth for arithmetic reasons.** That alone would produce a
deep-minus-light difference of the wrong sign in one arm and nothing biological need be happening.

    **P1  If band placement drives the inversion, then restricting to cases whose deep alpha peak is NOT
          at the band floor must ATTENUATE the inversion — by more than removing the same number of cases
          at random does.**

=========================================================================================================
WHY THE COMPARISON IS AGAINST A MATCHED-SIZE NULL AND NOT AGAINST THE FULL COHORT
=========================================================================================================
The restriction is **not symmetric**, and pretending otherwise would be the whole error. It removes 2 of 44
propofol cases and roughly 28 of 71 sevoflurane cases: it is in effect a sevoflurane-arm restriction. A gap
computed on a smaller and differently-composed arm differs from the full-cohort gap for reasons that have
nothing to do with alpha peaks.

Catalogue rule 35 says exactly what to do: **resample a matched subset that is NOT subset on the variable of
interest.** So the reference here is a distribution of `Δ` over random subsets drawn to the SAME arm-wise
sizes, ignoring the peak entirely. The real restriction is read against that distribution, never against the
full cohort, and the question becomes "was it WHO was removed" rather than "how many".

=========================================================================================================
STATISTIC
=========================================================================================================
For each case, `d = deep_<feature> - light_<feature>` on the raw per-case medians. The arm gap is the
difference in the fraction of cases with `d > 0`:

    G(S) = frac(d > 0 | sevoflurane, S) - frac(d > 0 | propofol, S)

A sign-based gap is used rather than a mean difference because the claim is about DIRECTION, and because the
features are on incomparable scales. `s = sign(G_full)` is fixed once, in G2, on the full cohort — before
any restriction — and every gap is reported oriented as `g(S) = s * G(S)`, so "attenuation" always means a
DECREASE and no folded statistic is compared across different rows (rule 46).

    **PRIMARY:  Δ = g(restricted) - g(full),  read as a percentile of the matched-size null.**
    Band placement predicts Δ < 0 and a percentile below 5.

=========================================================================================================
GATES
=========================================================================================================
G1  >= 25 cases per arm survive the restriction, or an attenuation is a sample-size statement.
G2  **THE INVERSION MUST BE ALIVE** (rule 53). `|G_full|` must exceed the 95th percentile of its own
    arm-label permutation null. If there is no inversion in this cohort, explaining one is meaningless —
    which is the gate E208 died on and E61 had to add after the fact.
G3  **THE RESTRICTION MUST BE ARM-SPECIFIC.** The floor-pinning rate must differ between arms by more than
    its own arm-label permutation null's 95th percentile. If both arms pin equally, the restriction removes
    nothing agent-specific and cannot explain an agent contrast.
G4  **PLACEBO, AND IT GATES THE VERDICT.** Pinning at the alpha floor is plausibly a marker of deeper or
    more pathological suppression generally, in which case restricting on it would attenuate ANY feature's
    arm gap. So the identical Δ and percentile are computed for four features with no arithmetic dependence
    on where the alpha peak sits — `lempel_ziv`, `whole_head_exponent`, `spectral_entropy`,
    `relative_delta_power`. If any of them attenuates as extremely as `relative_alpha_power`, the finding is
    about the stratum and not about the band. The placebo is a COMPARISON against the real effect, never an
    absolute threshold (rule 34).

**DECLARED POSITIVE CONTROL, DESCRIPTIVE AND NOT A GATE.** If the mechanism is real, power lost from the
bottom of the alpha box has to land in the box below it: theta is 4-8 Hz and sits directly beneath. So
`relative_theta_power` should show the MIRROR pattern. It is reported beside the primary and deliberately
does not gate anything, because a gate revised or added around a control that misbehaves is the move rule 58
forbids — and because the skirt of a peak at 8.0 Hz is not guaranteed to reach below 8 Hz at all.

=========================================================================================================
VERDICT — WRONG-DIRECTION CASES FIRST (rule 37)
=========================================================================================================
  (1) NOT INTERPRETABLE   G1, G2 or G3 fails. Nothing below may be read.
  (2) AMPLIFIED           Δ lies ABOVE the 95th percentile of the matched-size null. Restricting to cases
                          whose peak is inside the band makes the inversion LARGER. That REFUTES band
                          placement and is reported as its own outcome, not as a weak version of support.
  (3) CONFOUNDED BY DEPTH Δ is below the 5th percentile, but at least one placebo feature is at least as
                          extreme. The restriction is selecting deep or pathological cases generally.
  (4) ABSENT              Δ sits inside the null's central range. Band placement is not supported and the
                          peak-shift observation remains descriptive only.
  (5) BAND PLACEMENT      Δ below the 5th percentile AND strictly more extreme than every placebo feature.

**REGISTERED PREDICTION: (5) BAND PLACEMENT, and I hold it weakly.** The arithmetic is not in doubt — a
fixed window under-counts a peak on its edge — but whether it accounts for enough of the gap to move a
sign-rate is a quantitative question this design has not pre-computed. **(3) is a live and unembarrassing
outcome**: floor-pinning at depth is a plausible marker of deeper suppression, the two arms differ in depth
achieved, and that is precisely what the placebo exists to detect. **(2) would be the most valuable**,
because it would mean the inversion is *stronger* where the measure is least distorted, and the aetiology
of `relative_alpha_power`'s double failure would have to be biological after all.

**SCOPE, STATED IN ADVANCE.** This experiment can show that the fixed band distorts the contrast. It CANNOT
show what a correctly-anchored measure would find, because no peak-anchored band power exists in this
deposit and the per-window spectra were never stored — only scalar summaries. Building one requires
re-extraction and is a successor, not a rescue clause for this file.

    python bsde/src/bsde/experiments/e213_alpha_band_placement.py
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, HERE)

import e186_prespecified_clean_subset as E186                                   # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e213_alpha_band_placement.json")

SEED = 20260802
PRIMARY = "relative_alpha_power"
PLACEBO = ("lempel_ziv", "whole_head_exponent", "spectral_entropy", "relative_delta_power")
POSITIVE_CONTROL = "relative_theta_power"
BAND_LO = 8.0
MIN_PER_ARM = 25
N_NULL = 4000
N_PERM = 4000


def gap(d, arm, sel):
    """G(S) = frac(d>0 | sevo, S) - frac(d>0 | propofol, S)."""
    a = sel & (arm > 0.5) & np.isfinite(d)
    b = sel & (arm < 0.5) & np.isfinite(d)
    if a.sum() == 0 or b.sum() == 0:
        return float("nan")
    return float(np.mean(d[a] > 0) - np.mean(d[b] > 0))


def main() -> int:
    print("E213 — is the relative_alpha_power inversion a BAND-PLACEMENT artefact?")
    cases = E186.load("exposure")
    ids = sorted(cases)
    n = len(ids)
    arm = np.array([cases[c]["arm"] for c in ids], float)
    peak = np.array([cases[c]["deep_alpha_peak_hz"] for c in ids], float)

    feats = [PRIMARY, *PLACEBO, POSITIVE_CONTROL]
    D = {f: np.array([cases[c][f"deep_{f}"] - cases[c][f"light_{f}"] for c in ids], float)
         for f in feats}

    # The pinning threshold is DERIVED, not chosen (rule 63): one PSD frequency bin above the band floor,
    # where the bin width is measured as the smallest positive gap between distinct observed peak values.
    u = np.unique(peak[np.isfinite(peak)])
    binw = float(np.diff(u)[np.diff(u) > 0].min()) if u.size > 1 else 0.0
    thr = BAND_LO + binw
    pinned = np.isfinite(peak) & (peak <= thr + 1e-9)
    keep = np.isfinite(peak) & ~pinned
    full = np.ones(n, bool)

    nsA, nsB = int((keep & (arm > 0.5)).sum()), int((keep & (arm < 0.5)).sum())
    print(f"   {n} cases: {int(arm.sum())} sevoflurane, {int(n - arm.sum())} propofol")
    print(f"   PSD bin width measured at {binw:.3f} Hz -> pinned means deep peak <= {thr:.3f} Hz")
    print(f"   pinned: sevoflurane {np.mean(pinned[arm > 0.5]):.4f}   "
          f"propofol {np.mean(pinned[arm < 0.5]):.4f}")
    print(f"   restricted cohort: {nsA} sevoflurane, {nsB} propofol")

    g1 = bool(min(nsA, nsB) >= MIN_PER_ARM)
    print(f"G1 >= {MIN_PER_ARM} per arm after restriction   {'PASS' if g1 else '*** FAIL'}")

    # ---- G2: the inversion must be alive -------------------------------------------------------------
    G_full = gap(D[PRIMARY], arm, full)
    rng = np.random.default_rng(SEED)
    perm = np.array([abs(gap(D[PRIMARY], rng.permutation(arm), full)) for _ in range(N_PERM)])
    p95 = float(np.quantile(perm, 0.95))
    g2 = bool(abs(G_full) > p95)
    print(f"G2 INVERSION ALIVE  G_full {G_full:+.4f}  |G| {abs(G_full):.4f} vs arm-permutation p95 "
          f"{p95:.4f}   {'PASS' if g2 else '*** FAIL'}")
    s = 1.0 if G_full >= 0 else -1.0

    # ---- G3: the restriction must be arm-specific ----------------------------------------------------
    pin_gap = float(np.mean(pinned[arm > 0.5]) - np.mean(pinned[arm < 0.5]))
    pperm = np.array([abs(float(np.mean(pinned[a > 0.5]) - np.mean(pinned[a < 0.5])))
                      for a in (rng.permutation(arm) for _ in range(N_PERM))])
    pp95 = float(np.quantile(pperm, 0.95))
    g3 = bool(abs(pin_gap) > pp95)
    print(f"G3 RESTRICTION ARM-SPECIFIC  pinning gap {pin_gap:+.4f} vs permutation p95 {pp95:.4f}   "
          f"{'PASS' if g3 else '*** FAIL'}")

    # ---- primary and placebo, each against the SAME matched-size null --------------------------------
    idxA = np.flatnonzero(arm > 0.5)
    idxB = np.flatnonzero(arm < 0.5)
    subsets = []
    for r in range(N_NULL):
        g = np.random.default_rng(SEED + 900 + r)
        m = np.zeros(n, bool)
        m[g.choice(idxA, size=nsA, replace=False)] = True
        m[g.choice(idxB, size=nsB, replace=False)] = True
        subsets.append(m)

    out = {}
    print(f"\n{'feature':<24s} {'g_full':>8s} {'g_restr':>8s} {'delta':>8s} {'pctile':>7s} {'role':>9s}")
    for f in feats:
        gf = s * gap(D[f], arm, full) if f == PRIMARY else None
        # every feature is oriented by ITS OWN full-cohort gap, so "attenuation" is a decrease for all
        sf = 1.0 if gap(D[f], arm, full) >= 0 else -1.0
        gfull = sf * gap(D[f], arm, full)
        grest = sf * gap(D[f], arm, keep)
        delta = grest - gfull
        nulls = np.array([sf * gap(D[f], arm, m) - gfull for m in subsets])
        pct = float(np.mean(nulls <= delta) * 100.0)
        role = "PRIMARY" if f == PRIMARY else ("pos-ctrl" if f == POSITIVE_CONTROL else "placebo")
        out[f] = {"orient": sf, "g_full": gfull, "g_restricted": grest, "delta": delta,
                  "null_percentile": pct, "null_p05": float(np.quantile(nulls, 0.05)),
                  "null_p95": float(np.quantile(nulls, 0.95)), "role": role}
        print(f"{f:<24s} {gfull:>+8.4f} {grest:>+8.4f} {delta:>+8.4f} {pct:>6.1f}% {role:>9s}")
        _ = gf

    res = {"experiment": "E213", "n_cases": n, "n_sevo": int(arm.sum()),
           "n_propofol": int(n - arm.sum()), "bin_width_hz": binw, "pin_threshold_hz": thr,
           "pinned_rate_sevo": float(np.mean(pinned[arm > 0.5])),
           "pinned_rate_propofol": float(np.mean(pinned[arm < 0.5])),
           "n_restricted": {"sevoflurane": nsA, "propofol": nsB},
           "G_full_primary": G_full, "orientation_sign": s,
           "g1": g1, "g2": g2, "g3": g3, "features": out}

    d_real = out[PRIMARY]["delta"]
    p_real = out[PRIMARY]["null_percentile"]
    worst_placebo = max(PLACEBO, key=lambda f: -out[f]["null_percentile"])
    p_plac = out[worst_placebo]["null_percentile"]

    print("\n" + "=" * 100)
    if not (g1 and g2 and g3):
        v_, why = "NOT INTERPRETABLE", ("a gate failed: " + ", ".join(
            nm for nm, ok in (("G1 restricted size", g1), ("G2 inversion alive", g2),
                              ("G3 restriction arm-specific", g3)) if not ok))
    elif p_real >= 95.0:
        v_, why = "AMPLIFIED", (
            f"restricting to cases whose alpha peak is INSIDE the band made the inversion LARGER "
            f"(delta {d_real:+.4f}, {p_real:.1f}th percentile of the matched-size null). Band placement is "
            "REFUTED: the contrast is strongest where the measure is least distorted")
    elif p_real > 5.0:
        v_, why = "ABSENT", (
            f"delta {d_real:+.4f} sits at the {p_real:.1f}th percentile of the matched-size null, i.e. "
            "inside its central range. Removing the floor-pinned cases does no more than removing the same "
            "number at random, so band placement is not supported and the peak shift stays descriptive")
    elif p_plac <= p_real:
        v_, why = "CONFOUNDED BY DEPTH", (
            f"the primary attenuates ({d_real:+.4f}, {p_real:.1f}th percentile) but the placebo feature "
            f"{worst_placebo} attenuates at least as extremely ({out[worst_placebo]['delta']:+.4f}, "
            f"{p_plac:.1f}th percentile). Floor-pinning is selecting deeply suppressed cases generally, "
            "not distorting the alpha band specifically")
    else:
        v_, why = "BAND PLACEMENT", (
            f"delta {d_real:+.4f} at the {p_real:.1f}th percentile of the matched-size null, strictly more "
            f"extreme than every placebo feature (best placebo {worst_placebo} at {p_plac:.1f}%). The "
            "inversion is substantially an artefact of measuring a moving peak through a fixed 8-13 Hz "
            "window")
    res["verdict"], res["why"] = v_, why
    print(f"VERDICT: {v_}\n  {why}")
    pc = out[POSITIVE_CONTROL]
    print(f"\nDECLARED POSITIVE CONTROL (descriptive, gates nothing): {POSITIVE_CONTROL} "
          f"delta {pc['delta']:+.4f} at the {pc['null_percentile']:.1f}th percentile. Power lost from the "
          f"bottom of the alpha box lands in theta if the mechanism is real.")
    print("=" * 100)
    print("SCOPE: this file can show the fixed band distorts the contrast. It CANNOT show what a\n"
          "  peak-anchored measure would find -- no per-window spectra were stored, only scalar\n"
          "  summaries, so a corrected band power needs re-extraction and is a successor.")

    os.makedirs(RESULTS, exist_ok=True)
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
