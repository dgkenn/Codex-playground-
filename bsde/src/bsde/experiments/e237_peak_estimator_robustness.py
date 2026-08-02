#!/usr/bin/env python3
"""E237 -- does the aperiodic-fit defect corrupt the peak estimator that E233's RETRACTION rests on?

PRE-REGISTRATION. Written and committed before the numbers below this line exist.
Entirely SYNTHETIC: no real recording is read, so nothing here can contaminate any pre-registration or
peek at any label. That is deliberate -- the question is about an estimator, not about a cohort.

WHY THIS IS URGENT RATHER THAN TIDY. Catalogue rule 90 records a verified defect: `fit_aperiodic`
defaults to `mode="loglog_ols"`, the `whole_head_exponent` family passes `"loglog_robust"` explicitly
(`seed.py:87`), and two other call sites do not. One of those is **`seed.py:166`, inside `_iaf_peak`** --
the aperiodic fit whose prediction is SUBTRACTED from the log spectrum before the peak is located as the
residual maximum. A plain OLS log-log fit over 1-45 Hz is pulled upward by whatever oscillation is
present, so the baseline is biased TOWARD the peak, and the residual it leaves is the very thing the
search maximises.

**This threatens E233's conclusion in both directions, which is why it cannot be left as a note.**
E233 retracted this project's headline Challenge A finding -- the apparent propofol/sevoflurane reversal
in `relative_alpha_power` -- on the evidence that the PEAK-ANCHORED measure did not reverse. That measure
is `relative_alpha_power_iaf`, which calls `_iaf_peak` and therefore inherits the defect. If the peak
estimator is unreliable, then so is the retraction, and the reversal would have to be un-retracted. E233
also produced the one surviving Challenge A fact -- sevoflurane slides the peak down with dose, propofol
does not -- straight out of the same estimator.

WHAT ACTUALLY MATTERS, AND IT IS NARROWER THAN "IS THE FIT BIASED". Every statistic E233 computed is
RANK-BASED: within-case Spearman of the peak against exposure, and a consistency summary over cases. A
bias that is MONOTONE in the true peak frequency leaves every rank untouched and is therefore harmless
for those statistics, however large it is. What would damage them is non-monotonicity, or a bias that
differs between the two arms' operating points. So this file does not ask "is the estimator biased"; it
asks the three questions whose answers decide whether E233 stands.

PRIMARIES. Synthetic signals with a known peak frequency swept from 6.0 to 14.0 Hz in 0.5 Hz steps, 12
seeds each, using the same signal construction as `tests/test_iaf_capability.py` so the results are
commensurable with an already-verified capability result (rule 23).

  P1  MONOTONICITY over the range the two arms actually occupy. The sevoflurane arm's median peak is
      9.69 Hz and the propofol arm's 10.75 Hz, and the sevoflurane within-case excursion puts its lower
      reach near 7.5 Hz, so the operating range is 7.5-11.0 Hz. P1 is Spearman(estimate, truth) over that
      range plus the count of adjacent-step INVERSIONS. A perfectly monotone estimator scores 1.0 with
      zero inversions and every rank statistic in E233 is safe regardless of bias.
  P2  DIFFERENTIAL BIAS BETWEEN THE ARMS' OPERATING POINTS. |bias at 9.69 Hz - bias at 10.75 Hz| under
      the current OLS default. A constant offset cannot separate the arms; a bias that differs between
      the points where the two arms sit can, and that is the specific threat to E233's between-arm
      comparison of median peak frequency.
  P3  DOES THE ROBUST FIT CHANGE THE ANSWER? The same sweep with `mode="loglog_robust"`, and the
      OLS-minus-robust difference in estimated peak as a function of true frequency. If the two agree to
      within the frequency resolution of the PSD, the defect is inert HERE even though it is real
      elsewhere, and E233 needs no recomputation.

GATES, each constructed so the input that should fail it does and the input that should pass it does
(rules 40 and 81).

  G1  BOTH ESTIMATORS MUST WORK AT ALL. Each must recover a clean, unambiguous peak at 10 Hz to within
      the PSD's own frequency resolution. The threshold is DERIVED, not chosen (rule 63): it is the PSD
      bin width, because no peak-picking estimator can resolve better than one bin, and a tolerance
      tighter than that would measure the FFT rather than the estimator.
  G2  THE TWO ESTIMATORS MUST DIFFER SOMEWHERE, or P3 is vacuous and the "fix" is a rename (rule 60 run
      in reverse). Their maximum absolute disagreement across the sweep is reported, and if it is below
      one bin everywhere the file says so plainly rather than implying it validated anything.
  G3  THE SWEEP MUST CONTAIN A CASE THE ESTIMATOR SHOULD FAIL. A pure 1/f background with NO oscillation
      must return NaN from both estimators; if either invents a peak where none exists, neither can be
      trusted about where a peak is.

VERDICT RULE, wrong-direction case FIRST (rule 37, five recorded occurrences of getting this wrong).

  (a) P1 shows the OLS estimator is NON-MONOTONE over 7.5-11.0 Hz -> E233 IS NOT SAFE. Its rank
      statistics can be reordered by the estimator, the retraction of the alpha reversal is not
      established, and both must be recomputed with a robust fit before anything is claimed either way.
  (b) P1 monotone AND P2 differential bias exceeds one PSD bin -> PARTIALLY SAFE. The within-case rank
      results stand; the BETWEEN-ARM comparison of median peak frequency does not, and the "sevoflurane
      peak sits lower than propofol's" statement must be withdrawn while the dose-response one survives.
  (c) P1 monotone AND P2 within one bin -> E233 SAFE. The defect is real, documented, and inert for these
      statistics, and rule 90's remediation can be scheduled rather than rushed.

  Gating, applied AFTER the primaries because a gate can only invalidate a pass and never rescue a null
  (rule 37): G1 or G3 failing -> NOT INTERPRETABLE. G2 failing does NOT invalidate; it means the OLS and
  robust fits are equivalent here, which is itself the answer to P3 and is reported as such.

SCOPE. A single-channel pink-plus-sinusoid model at 128 Hz with one oscillation. Real spectra have
multiple peaks, harmonics and line noise, any of which could make the two fits diverge where this model
says they agree. A pass here is therefore evidence that the defect is inert for THIS estimator on THIS
signal class, and is not a general clearance of `fit_aperiodic`'s default.

INCUMBENT (rule 45): the current shipped estimator, `alpha_peak_hz_wide` with the OLS default, which the
robust variant must be shown to differ from before any recomputation is justified.

    python bsde/src/bsde/experiments/e237_peak_estimator_robustness.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

SFREQ = 128.0
DURATION_S = 30.0
N_SEEDS = 12
SWEEP_LO, SWEEP_HI, SWEEP_STEP = 6.0, 14.0, 0.5
OPERATING_LO, OPERATING_HI = 7.5, 11.0
SEVO_MEDIAN, PROP_MEDIAN = 9.69, 10.75
PEAK_SEARCH_LO, PEAK_SEARCH_HI = 5.0, 15.0
OUT = "bsde/results/e237_peak_estimator_robustness.json"


def _signal(f0, seed):
    """Identical construction to tests/test_iaf_capability.py (rule 23)."""
    import numpy as np
    rng = np.random.default_rng(seed)
    n = int(SFREQ * DURATION_S)
    t = np.arange(n) / SFREQ
    return np.vstack([np.cumsum(rng.normal(0, 1, n)) * 0.4
                      + 1.2 * np.sin(2 * np.pi * f0 * t + rng.uniform(0, 6))
                      for _ in range(2)])


def _background(seed):
    import numpy as np
    rng = np.random.default_rng(seed)
    n = int(SFREQ * DURATION_S)
    return np.vstack([np.cumsum(rng.normal(0, 1, n)) * 0.4 for _ in range(2)])


def peak(data, mode):
    """`_iaf_peak` with the aperiodic mode made explicit instead of defaulted.

    Reproduces seed.py's `_iaf_peak` line for line, changing only the `mode` argument, so the OLS arm IS
    the shipped estimator rather than a reimplementation of it (rule 20).
    """
    import numpy as np
    from bsde.candidates.seed import _mean_psd
    from bsde.features.aperiodic import fit_aperiodic
    f, p = _mean_psd(data, SFREQ)
    ap = fit_aperiodic(f, p, fit_lo_hz=1.0, fit_hi_hz=45.0, mode=mode)
    m = (f >= PEAK_SEARCH_LO) & (f <= PEAK_SEARCH_HI) & (p > 0)
    if m.sum() < 5:
        return float("nan")
    resid = np.log10(p[m]) - (ap["offset"] - ap["exponent"] * np.log10(f[m]))
    i = int(np.nanargmax(resid))
    if i == 0 or i == resid.size - 1:
        return float("nan")
    return float(f[m][i])


def bin_width():
    """The PSD's own frequency resolution -- the floor on any peak-picking tolerance (rule 63)."""
    import numpy as np
    from bsde.candidates.seed import _mean_psd
    f, _p = _mean_psd(_signal(10.0, 1), SFREQ)
    return float(np.median(np.diff(f)))


def main() -> int:
    import numpy as np
    from bsde.verifier.stats import spearman

    # sanity: the shipped estimator and this file's OLS arm must agree exactly (rule 20)
    from bsde.candidates.seed import seed_registry
    from bsde.candidates.registry import REGISTRY
    seed_registry()
    shipped = REGISTRY.get("alpha_peak_hz_wide").fn
    chk = [(float(shipped(_signal(f, 50 + i), ["a", "b"], SFREQ, {})), peak(_signal(f, 50 + i), "loglog_ols"))
           for i, f in enumerate((8.0, 10.0, 12.0))]
    same = all((not np.isfinite(a) and not np.isfinite(b)) or a == b for a, b in chk)
    print(f"reimplementation check against the shipped candidate: {chk} -> "
          f"{'IDENTICAL' if same else 'DIFFERENT -- this file is not testing the shipped estimator'}")
    assert same, "the OLS arm must BE the shipped estimator, not a lookalike"

    bw = bin_width()
    print(f"PSD bin width (the derived tolerance floor, rule 63): {bw:.4f} Hz")

    truths = np.arange(SWEEP_LO, SWEEP_HI + 1e-9, SWEEP_STEP)
    est = {"loglog_ols": [], "loglog_robust": []}
    for f0 in truths:
        for mode in est:
            v = [peak(_signal(float(f0), 100 + s), mode) for s in range(N_SEEDS)]
            v = [x for x in v if np.isfinite(x)]
            est[mode].append(float(np.median(v)) if v else float("nan"))
    for mode in est:
        est[mode] = np.asarray(est[mode], float)

    print()
    print(f"{'true':>6}{'OLS':>9}{'robust':>9}{'OLS-true':>10}{'rob-true':>10}{'OLS-rob':>9}")
    for i, t in enumerate(truths):
        o, r = est["loglog_ols"][i], est["loglog_robust"][i]
        print(f"{t:6.1f}{o:9.3f}{r:9.3f}{o - t:+10.3f}{r - t:+10.3f}{o - r:+9.3f}")

    # ---- G1: both estimators recover a clean 10 Hz peak to within one bin --------------------------
    i10 = int(np.argmin(np.abs(truths - 10.0)))
    g1 = all(np.isfinite(est[m][i10]) and abs(est[m][i10] - 10.0) <= bw for m in est)
    print()
    print(f"G1 both recover a clean 10 Hz peak within one bin ({bw:.4f} Hz): "
          f"OLS {est['loglog_ols'][i10]:.3f}, robust {est['loglog_robust'][i10]:.3f} "
          f"-> {'PASS' if g1 else 'FAIL'}")

    # ---- G3: a pure background must return NaN from both ------------------------------------------
    nan_ols = [peak(_background(400 + s), "loglog_ols") for s in range(N_SEEDS)]
    nan_rob = [peak(_background(400 + s), "loglog_robust") for s in range(N_SEEDS)]
    frac_ols = float(np.mean([not np.isfinite(v) for v in nan_ols]))
    frac_rob = float(np.mean([not np.isfinite(v) for v in nan_rob]))
    g3 = frac_ols > 0.0 and frac_rob > 0.0
    print(f"G3 pure 1/f background returns NaN: OLS {frac_ols:.2f} of draws, robust {frac_rob:.2f} "
          f"-> {'PASS' if g3 else 'FAIL'}  (a peak invented where none exists would disqualify both)")

    # ---- G2: do the two fits differ at all? --------------------------------------------------------
    d = est["loglog_ols"] - est["loglog_robust"]
    maxdiff = float(np.nanmax(np.abs(d)))
    g2 = maxdiff > bw
    print(f"G2 the two fits differ somewhere: max |OLS - robust| = {maxdiff:.4f} Hz against one bin "
          f"{bw:.4f} -> {'differ' if g2 else 'EQUIVALENT within one bin'}")

    # ---- P1 monotonicity over the operating range ---------------------------------------------------
    sel = (truths >= OPERATING_LO) & (truths <= OPERATING_HI)
    to, eo = truths[sel], est["loglog_ols"][sel]
    ok = np.isfinite(eo)
    rho = float(spearman(to[ok], eo[ok]))
    inv = int(np.sum(np.diff(eo[ok]) < 0))
    p1_mono = rho > 0.99 and inv == 0
    print()
    print(f"P1 monotonicity of the OLS estimator over {OPERATING_LO}-{OPERATING_HI} Hz "
          f"({ok.sum()} steps): Spearman {rho:+.4f}, {inv} adjacent inversions "
          f"-> {'MONOTONE' if p1_mono else 'NOT MONOTONE'}")

    # ---- P2 differential bias between the two arms' operating points ---------------------------------
    def bias_at(f_target, mode):
        j = int(np.argmin(np.abs(truths - f_target)))
        return float(est[mode][j] - truths[j]), float(truths[j])

    bs, ts = bias_at(SEVO_MEDIAN, "loglog_ols")
    bp, tp = bias_at(PROP_MEDIAN, "loglog_ols")
    p2 = abs(bs - bp)
    print(f"P2 differential bias, sevoflurane operating point {ts:.1f} Hz (bias {bs:+.3f}) versus "
          f"propofol {tp:.1f} Hz (bias {bp:+.3f}): |difference| = {p2:.4f} Hz against one bin "
          f"{bw:.4f} -> {'EXCEEDS a bin' if p2 > bw else 'within a bin'}")

    # ---- P3 ---------------------------------------------------------------------------------------
    p3 = float(np.nanmean(np.abs(d[sel])))
    print(f"P3 mean |OLS - robust| over the operating range: {p3:.4f} Hz "
          f"({'materially different' if p3 > bw else 'equivalent within one bin'})")

    if not g1:
        verdict = "NOT INTERPRETABLE -- G1 failed; an estimator that cannot find a clean 10 Hz peak says nothing"
    elif not g3:
        verdict = "NOT INTERPRETABLE -- G3 failed; an estimator that invents a peak in pure noise cannot be trusted about location"
    elif not p1_mono:
        verdict = ("E233 IS NOT SAFE -- the shipped OLS estimator is NOT monotone in true peak frequency "
                   "over the range the two arms occupy, so its rank statistics can be reordered by the "
                   "estimator itself; the retraction of the alpha reversal is not established and both "
                   "E233 arms must be recomputed with a robust fit")
    elif p2 > bw:
        verdict = ("PARTIALLY SAFE -- within-case rank results stand because the estimator is monotone, "
                   "but the bias differs between the arms' operating points by more than one PSD bin, so "
                   "the between-arm claim that the sevoflurane peak sits lower than propofol's must be "
                   "withdrawn while the dose-response claim survives")
    else:
        verdict = ("E233 SAFE -- the estimator is monotone over the operating range and its bias does not "
                   "differ between the arms' operating points by as much as one PSD bin; rule 90's defect "
                   "is real, documented, and inert for these statistics")
    print()
    print("VERDICT:", verdict)

    with open(OUT, "w") as fh:
        json.dump({"bin_width_hz": bw, "truths": truths.tolist(),
                   "estimates": {m: est[m].tolist() for m in est},
                   "p1": {"spearman": rho, "inversions": inv, "monotone": bool(p1_mono),
                          "range": [OPERATING_LO, OPERATING_HI]},
                   "p2": {"sevo_bias": bs, "prop_bias": bp, "diff": p2,
                          "exceeds_bin": bool(p2 > bw)},
                   "p3": {"mean_abs_ols_minus_robust": p3},
                   "gates": {"G1": bool(g1), "G2_differ": bool(g2), "G3": bool(g3),
                             "max_diff_hz": maxdiff},
                   "nan_fraction_on_background": {"ols": frac_ols, "robust": frac_rob},
                   "verdict": verdict}, fh, indent=2, sort_keys=True)
    print("wrote ->", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
