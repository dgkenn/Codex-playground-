#!/usr/bin/env python3
"""E214 — does a measure's SENSITIVITY TO WHERE THE SPECTRUM SITS predict its failure to transport?

REGISTERED BEFORE THE INSTRUMENT SIDE EXISTS. **Read the disclosure below before the prediction.**

=========================================================================================================
WHAT E213 SETTLED AND WHAT IT LEFT
=========================================================================================================
E213 asked whether the propofol/sevoflurane inversion of `relative_alpha_power` is band placement, by
removing the cases whose alpha peak sits on the 8 Hz band floor. Against a matched-size null it returned
**ABSENT** (delta -0.0310, 18.8th percentile) and a placebo feature attenuated more than the primary. The
case-removal version of the story is dead.

That does not settle the general question, and the two are genuinely different. E213 removed CASES from one
measure. This file asks a question about MEASURES: **is a feature's disagreement between agents predicted by
how much its value depends on where in frequency the signal sits, as a property of the instrument?**

A measure defined as power inside fixed edges must change when a spectrum slides, even if nothing about the
brain state changed. A measure with no frequency landmarks — an aperiodic slope, a complexity count — need
not. Two anaesthetics that put the same state at different frequencies would therefore disagree on the first
kind and agree on the second, with no biology involved.

    **P1  Across the feature panel, FREQUENCY-SHIFT SENSITIVITY (measured on synthetic signals, with no
          real data involved) is POSITIVELY correlated with cross-agent transport failure (measured on
          VitalDB cases, with no synthetic data involved).**

=========================================================================================================
DISCLOSURE — THE TRANSPORT SIDE IS PARTLY VISIBLE, AND RULE 47 REQUIRES SAYING SO
=========================================================================================================
Rule 47 records that a placebo can show a choice is extreme but cannot show it was made blind, and that the
defence has to be structural and declared at registration. Here is the honest position.

**E213 printed the arm gap for six features before this file was written, and I have seen them**:
`relative_alpha_power` +0.3742, `relative_delta_power` +0.1805, `spectral_entropy` +0.1697,
`whole_head_exponent` +0.1665, `relative_theta_power` +0.1665, `lempel_ziv` +0.0186. That ordering is
already consistent with the hypothesis, and no amount of procedure undoes my having seen it.

The three things that make the test still worth running, all structural and all checkable in the code:

  1. **The instrument side does not exist yet and cannot be tuned to the outcome.** Frequency-shift
     sensitivity is computed on SYNTHETIC signals — pink noise plus a narrowband oscillation whose centre
     frequency is swept — that contain no patient, no agent and no deposit. There is no channel through
     which the transport numbers could influence it.
  2. **The code computes and PRINTS the full sensitivity table before it loads a single real case**, and
     that ordering is committed with the file. The pre-commitment is enforced by execution order, not by
     assertion.
  3. **Roughly two thirds of the panel is unseen.** Six of ~18 features' gaps are known to me; the rest,
     and every connectivity, entropy and artefact measure, are not.

The result is therefore reported as **partly confirmatory of an ordering already observed**, and it is not
independent evidence at the strength a fully blind test would carry. That sentence belongs in any write-up.

=========================================================================================================
THE TWO SIDES
=========================================================================================================
**INSTRUMENT SIDE (synthetic).** 19 channels, 200 Hz, 60 s. A shared 1/f^1.5 aperiodic background plus a
per-channel independent component, plus a narrowband oscillation whose centre frequency `f0` is swept over
7.0-12.0 Hz at fixed oscillatory power, `N_SEEDS` realisations per step. For each feature,

    S = |Spearman(f0, value)|  over the whole sweep

is its frequency-shift sensitivity: how much the measure moves when the spectrum slides and nothing else
changes.

**PLACEBO INSTRUMENT PROPERTY (synthetic).** The identical sweep is run on overall GAIN at fixed `f0`,
giving `A = |Spearman(gain, value)|`. Amplitude sensitivity is a property every one of these measures could
have, and it has no reason whatever to predict how two anaesthetics compare. If `A` predicts transport
failure as well as `S` does, the finding is not about frequency and G4 refuses it (rule 34 — a placebo is a
comparison against the real effect, never a threshold).

**TRANSPORT SIDE (real).** E213's statistic unchanged, on E186's 115 clean single-agent VitalDB cases:
`G = frac(deep-light > 0 | sevoflurane) - frac(deep-light > 0 | propofol)`. Transport FAILURE is `|G|`,
**bias-corrected by subtracting that feature's own arm-permutation median**, because a folded statistic is
biased upward under the null and the bias differs with a feature's missingness (rule 46).

=========================================================================================================
GATES
=========================================================================================================
G1  BOTH FAMILIES MUST BE POPULATED, against a DERIVED floor rather than a round number (rule 63). The null
    distribution of `S` is measured by permuting `f0` against the values, and at least `MIN_PER_FAMILY`
    features must sit above its 95th percentile and at least `MIN_PER_FAMILY` below its median. A panel that
    is all one family cannot support a correlation across families.
G2  **TRANSPORT FAILURE MUST EXIST** (rule 53). At least `MIN_ALIVE` features must have `|G|` above their
    own arm-permutation 95th percentile. If nothing fails to transport, predicting failure is vacuous.
G3  at least `MIN_MATCHED` features must be computable on BOTH sides. A feature that returns NaN on
    synthetic data is reported as excluded, never silently dropped (rules 14 and 74).
G4  **PLACEBO GATES THE VERDICT**: the amplitude-sensitivity correlation must be strictly weaker than the
    frequency-sensitivity correlation.

=========================================================================================================
VERDICT — WRONG-DIRECTION CASES FIRST (rule 37)
=========================================================================================================
  (1) NOT INTERPRETABLE  G1, G2 or G3 fails.
  (2) INVERTED           the primary correlation's null percentile is at or below 5, i.e. frequency-sensitive
                         measures transport BETTER. This refutes the hypothesis outright and is reported as
                         its own outcome, never as weak support — the failure rule 37 was written for.
  (3) NOT FREQUENCY-SPECIFIC  the primary clears its null but the amplitude placebo is at least as strong.
                         Whatever is predicted, it is not about frequency.
  (4) ABSENT             the primary's percentile is inside the null's central range.
  (5) FREQUENCY PREDICTS TRANSPORT  the primary is above the 95th percentile of its null AND strictly
                         stronger than the amplitude placebo.

**REGISTERED PREDICTION: (4) ABSENT.** E213 has just refuted the case-level version of this mechanism on the
one feature where it should have been easiest to see, and that lowers the prior more than the visible
ordering raises it. The panel is also small — the correlation is over ~18 points — so the test is
underpowered by construction and an honest null is the most likely outcome. **(5) would be valuable and
must be reported with the disclosure above attached**; **(2) would be the most informative of all**, because
a measure that slides with the spectrum transporting BETTER would mean the agents differ in ways that a
frequency-blind measure is worse at tracking, which nothing in this programme currently predicts.

**SCOPE.** Transport here is between two anaesthetic agents in one deposit. Cross-DEPOSIT transport is a
different estimand and is not tested. `S` is measured against a single synthetic generator; a feature could
be frequency-sensitive in ways this generator does not excite, so a low `S` is weak evidence of invariance
whereas a high `S` is strong evidence of sensitivity. The asymmetry is stated rather than hidden.

    python bsde/src/bsde/experiments/e214_frequency_sensitivity_transport.py
"""

from __future__ import annotations

import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, HERE)

from bsde.verifier.stats import spearman                                        # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e214_frequency_sensitivity_transport.json")

SEED = 20260802
SFREQ = 200.0
DURATION_S = 60.0
N_CH = 19
F0_GRID = np.arange(7.0, 12.01, 0.5)
GAIN_GRID = np.array([0.5, 0.7, 1.0, 1.4, 2.0, 2.8])
GAIN_F0 = 10.0
N_SEEDS = 6
OSC_FRACTION = 0.35            # fraction of total variance in the oscillation
APERIODIC_EXPONENT = 1.5

MIN_PER_FAMILY = 3
MIN_ALIVE = 3
MIN_MATCHED = 10
N_PERM = 4000
N_SPERM = 20000


def synth(f0, gain, seed):
    """19-channel pink-noise background plus a narrowband oscillation at `f0`, scaled by `gain`."""
    g = np.random.default_rng(seed)
    n = int(SFREQ * DURATION_S)
    freqs = np.fft.rfftfreq(n, 1.0 / SFREQ)
    shape = np.zeros_like(freqs)
    shape[1:] = freqs[1:] ** (-APERIODIC_EXPONENT / 2.0)

    def pink(rng):
        ph = rng.uniform(0, 2 * np.pi, freqs.size)
        spec = shape * np.exp(1j * ph)
        x = np.fft.irfft(spec, n)
        return x / (x.std() + 1e-12)

    shared = pink(g)
    t = np.arange(n) / SFREQ
    X = np.empty((N_CH, n))
    for c in range(N_CH):
        bg = 0.6 * shared + 0.8 * pink(g)
        bg /= (bg.std() + 1e-12)
        # a narrowband oscillation: a sinusoid with slowly drifting phase, so it has finite bandwidth
        drift = np.cumsum(g.normal(0, 0.02, n))
        osc = np.sin(2 * np.pi * f0 * t + drift + g.uniform(0, 2 * np.pi))
        osc /= (osc.std() + 1e-12)
        a = math.sqrt(OSC_FRACTION)
        X[c] = gain * (math.sqrt(1.0 - OSC_FRACTION) * bg + a * osc) * 20.0   # microvolt-ish scale
    return X


def evaluate(names, X, ch, meta):
    from bsde.candidates.registry import REGISTRY
    out = {}
    for nm in names:
        try:
            v = float(REGISTRY.get(nm).fn(X, ch, SFREQ, meta))
        except Exception:
            v = float("nan")
        out[nm] = v
    return out


def gap(d, arm):
    a = (arm > 0.5) & np.isfinite(d)
    b = (arm < 0.5) & np.isfinite(d)
    if a.sum() == 0 or b.sum() == 0:
        return float("nan")
    return float(np.mean(d[a] > 0) - np.mean(d[b] > 0))


def main() -> int:
    print("E214 — does frequency-shift sensitivity predict cross-agent transport failure?")
    from bsde.candidates.seed import seed_registry
    names = [c.name for c in seed_registry()]
    ch = [f"C{i}" for i in range(N_CH)]
    meta = {}

    # ============ INSTRUMENT SIDE FIRST. No real data is loaded above this line or below it until the
    # ============ sensitivity table has been printed. The pre-commitment is the execution order.
    print(f"\nINSTRUMENT SIDE (synthetic only): sweeping f0 over {F0_GRID[0]}-{F0_GRID[-1]} Hz, "
          f"{N_SEEDS} realisations per step, {len(names)} registered candidates")
    f0v, vals = [], {nm: [] for nm in names}
    for f0 in F0_GRID:
        for s in range(N_SEEDS):
            r = evaluate(names, synth(float(f0), 1.0, SEED + 31 * int(f0 * 10) + s), ch, meta)
            f0v.append(float(f0))
            for nm in names:
                vals[nm].append(r[nm])
    gv, gvals = [], {nm: [] for nm in names}
    for gn in GAIN_GRID:
        for s in range(N_SEEDS):
            r = evaluate(names, synth(GAIN_F0, float(gn), SEED + 77 * int(gn * 10) + s), ch, meta)
            gv.append(float(gn))
            for nm in names:
                gvals[nm].append(r[nm])

    rng = np.random.default_rng(SEED)
    S, A, excluded = {}, {}, []
    for nm in names:
        v = np.array(vals[nm], float)
        w = np.array(gvals[nm], float)
        if np.isfinite(v).sum() < 0.8 * v.size or np.unique(v[np.isfinite(v)]).size < 3:
            excluded.append((nm, "not computable or constant on synthetic signals"))
            continue
        m = np.isfinite(v)
        S[nm] = abs(spearman(list(np.array(f0v)[m]), list(v[m])))
        mw = np.isfinite(w)
        A[nm] = abs(spearman(list(np.array(gv)[mw]), list(w[mw]))) if mw.sum() >= 6 else float("nan")

    # the null for S: permute f0 against a real feature's values, so the null carries the same tie structure
    ref = max(S, key=lambda k: S[k])
    rv = np.array(vals[ref], float)
    rm = np.isfinite(rv)
    snull = np.array([abs(spearman(list(rng.permutation(np.array(f0v)[rm])), list(rv[rm])))
                      for _ in range(N_SPERM // 20)])
    s95, s50 = float(np.quantile(snull, 0.95)), float(np.quantile(snull, 0.50))

    print(f"\n{'feature':<30s} {'S(freq)':>8s} {'A(gain)':>8s}")
    for nm in sorted(S, key=lambda k: -S[k]):
        print(f"{nm:<30s} {S[nm]:>8.4f} {A[nm]:>8.4f}")
    print(f"   S null (f0 permuted): p50 {s50:.4f}  p95 {s95:.4f}")
    if excluded:
        print("   EXCLUDED from the instrument side (reported, not dropped silently):")
        for nm, why in excluded:
            print(f"     {nm}: {why}")

    hi = [nm for nm in S if S[nm] > s95]
    lo = [nm for nm in S if S[nm] < s50]
    g1 = bool(len(hi) >= MIN_PER_FAMILY and len(lo) >= MIN_PER_FAMILY)
    print(f"G1 BOTH FAMILIES POPULATED  {len(hi)} above the S null's p95, {len(lo)} below its p50   "
          f"{'PASS' if g1 else '*** FAIL'}")

    # ============ TRANSPORT SIDE. Nothing above this line has touched a real recording. ================
    import e186_prespecified_clean_subset as E186
    cases = E186.load("exposure")
    ids = sorted(cases)
    arm = np.array([cases[c]["arm"] for c in ids], float)
    sample = cases[ids[0]]
    have = [nm for nm in S if f"deep_{nm}" in sample and f"light_{nm}" in sample]
    print(f"\nTRANSPORT SIDE: {len(ids)} cases; {len(have)} of {len(S)} instrument-side features are "
          f"present in the case table")

    Gc, alive = {}, []
    for nm in have:
        d = np.array([cases[c][f"deep_{nm}"] - cases[c][f"light_{nm}"] for c in ids], float)
        gobs = abs(gap(d, arm))
        nl = np.array([abs(gap(d, rng.permutation(arm))) for _ in range(N_PERM)])
        Gc[nm] = float(gobs - np.median(nl))
        if gobs > float(np.quantile(nl, 0.95)):
            alive.append(nm)
    g2 = bool(len(alive) >= MIN_ALIVE)
    g3 = bool(len(have) >= MIN_MATCHED)
    print(f"G2 TRANSPORT FAILURE EXISTS  {len(alive)} features above their own arm-permutation p95: "
          f"{sorted(alive)}   {'PASS' if g2 else '*** FAIL'}")
    print(f"G3 MATCHED PANEL >= {MIN_MATCHED}   {'PASS' if g3 else '*** FAIL'}")

    xs = [S[nm] for nm in have]
    ys = [Gc[nm] for nm in have]
    az = [A[nm] for nm in have]
    rho = spearman(xs, ys)
    rho_a = spearman([a for a in az], ys)
    nulls = np.array([spearman(list(rng.permutation(xs)), ys) for _ in range(N_SPERM)])
    pct = float(np.mean(nulls <= rho) * 100.0)
    nulls_a = np.array([spearman(list(rng.permutation(az)), ys) for _ in range(N_SPERM)])
    pct_a = float(np.mean(nulls_a <= rho_a) * 100.0)

    print(f"\n{'feature':<30s} {'S(freq)':>8s} {'|G|-corr':>9s}")
    for nm in sorted(have, key=lambda k: -Gc[k]):
        print(f"{nm:<30s} {S[nm]:>8.4f} {Gc[nm]:>+9.4f}")
    print(f"\nPRIMARY   Spearman(S, transport failure) = {rho:+.4f}   null percentile {pct:.1f}%")
    print(f"PLACEBO   Spearman(A_gain, transport failure) = {rho_a:+.4f}   null percentile {pct_a:.1f}%")
    g4 = bool(pct > pct_a)

    res = {"experiment": "E214", "n_cases": len(ids), "n_features_instrument": len(S),
           "n_features_matched": len(have), "excluded": excluded,
           "S": S, "A": A, "s_null_p50": s50, "s_null_p95": s95,
           "transport_failure": Gc, "alive": sorted(alive),
           "rho_primary": rho, "pct_primary": pct, "rho_placebo": rho_a, "pct_placebo": pct_a,
           "g1": g1, "g2": g2, "g3": g3, "g4": g4,
           "disclosure": ("the transport side is PARTLY VISIBLE: E213 printed the arm gap for six of these "
                          "features before this file was written. The instrument side is synthetic and was "
                          "computed and printed before any real case was loaded.")}

    print("\n" + "=" * 100)
    if not (g1 and g2 and g3):
        v_, why = "NOT INTERPRETABLE", ("a gate failed: " + ", ".join(
            nm for nm, ok in (("G1 both families populated", g1), ("G2 transport failure exists", g2),
                              ("G3 matched panel", g3)) if not ok))
    elif pct <= 5.0:
        v_, why = "INVERTED", (
            f"frequency-shift-sensitive measures transport BETTER, not worse (rho {rho:+.4f}, {pct:.1f}th "
            "percentile of the feature-label permutation null). The hypothesis is refuted outright")
    elif pct < 95.0:
        v_, why = "ABSENT", (
            f"rho {rho:+.4f} sits at the {pct:.1f}th percentile of the feature-label permutation null, "
            "inside its central range. How much a measure moves when the spectrum slides does not predict "
            "whether it disagrees between agents")
    elif not g4:
        v_, why = "NOT FREQUENCY-SPECIFIC", (
            f"the primary clears its null (rho {rho:+.4f}, {pct:.1f}th percentile) but the amplitude-gain "
            f"placebo does at least as well (rho {rho_a:+.4f}, {pct_a:.1f}th percentile). Whatever predicts "
            "transport failure here, it is not frequency specifically")
    else:
        v_, why = "FREQUENCY PREDICTS TRANSPORT", (
            f"rho {rho:+.4f} at the {pct:.1f}th percentile of the feature-label permutation null, and "
            f"strictly stronger than the amplitude-gain placebo ({rho_a:+.4f}, {pct_a:.1f}th). A measure's "
            "dependence on WHERE the spectrum sits predicts its disagreement between anaesthetics. "
            "REPORT WITH THE DISCLOSURE: six of these features' gaps were visible before registration")
    res["verdict"], res["why"] = v_, why
    print(f"VERDICT: {v_}\n  {why}")
    print("=" * 100)
    print("SCOPE: transport here is between two agents in ONE deposit; cross-deposit transport is a\n"
          "  different estimand and is not tested. A HIGH S is strong evidence of frequency sensitivity;\n"
          "  a LOW S is weak evidence of invariance, because one synthetic generator cannot excite every\n"
          "  way a measure might depend on frequency.")

    os.makedirs(RESULTS, exist_ok=True)
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
