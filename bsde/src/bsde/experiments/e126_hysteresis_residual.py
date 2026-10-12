"""E126 -- Is there a hysteresis the effect-site model CANNOT absorb? Testing neural inertia the only way
it is identifiable.

REGISTERED BEFORE ANY RISING/FALLING SPLIT HAS BEEN COMPUTED. E122's cohort, dose record and clock are
already built and checked; this file's question has not been run.

=========================================================================================================
WHY THIS IS THE ONE ACUTE PD LAYER WORTH TESTING, AND WHY IT MUST BE TESTED RATHER THAN FITTED
=========================================================================================================
The investigator asked whether an acute pharmacodynamic model can be stacked on top of the interaction
model. The candidate is NEURAL INERTIA -- the observation that induction occurs at higher effect-site
concentration than emergence, over and above equilibration. **Proekt and Kelz 2021 (Br J Anaesth
126:265-278, PMID 33081972) show it cannot be fitted as a layer**, and the quotation is the whole reason
this experiment has the shape it has:

    "one can always construct an effect-site equilibration model such that hysteresis collapses. So long
     as the concentration in the effect-site cannot be measured directly, the correct effect-site
     equilibration model and the one that erroneously collapses hysteresis are experimentally
     indistinguishable."

and, cutting the other way,

    "we also found that hysteresis can naturally arise even in a simple network of neurones independently
     of drug equilibration."

So a hysteresis parameter fitted on top of a ke0 model is unfalsifiable: any hysteresis can be absorbed
into the kinetics, and any kinetics can manufacture or destroy it. **The degeneracy breaks only with a
state measure that owes nothing to the drug model.** DOSE-I has one -- MOAA/S is assigned by a clinician
watching the patient, not computed from the infusion record -- and E122 has already built the pharmacology
arm against it. This is the identifiability-breaking measurement Proekt and Kelz say is required, and it is
available here and nowhere else in this project.

=========================================================================================================
DESIGN
=========================================================================================================
COHORT AND EXPOSURE: E122's, unchanged and imported rather than rebuilt (rule 20) -- 94 recordings, 25,102
windows, the same exclusions (extravasation, incomplete dose record), the same recovered per-recording
clock, the same 8-rate exponential basis. E122 established the pharmacology is alive here: out-of-bag rho
against MOAA/S climbs 0.1755 (cumulative dose) to 0.4595 (full rung).

DIRECTION is defined from the MODELLED concentration, not from the dose events, because that is what the
hypothesis is about. For each window, `dCe/dt` is the local slope of the L2 basis's fitted effect-site
signal; `RISING` and `FALLING` are its sign. Windows in the flat middle are NOT discarded -- a magnitude
threshold would be a free parameter (rule 63) -- instead the primary uses the signed slope directly.

    P1  THE PRIMARY. Fit the pharmacology (rung L2, out of bag by recording) and take the MOAA/S residual.
        Regress the residual on the SIGN of dCe/dt, clustered by recording. Neural inertia predicts a
        NON-ZERO coefficient with a specific sign: at matched concentration a patient going DOWN in
        concentration (emerging) should be MORE deeply sedated than the model expects -- i.e. a lower
        MOAA/S residual when falling. **That direction is fixed here, before the run.**

    P2  THE SAME TEST WITH THE INTERACTION MODEL'S POTENCY UNITS in place of the raw basis, so that the
        answer does not depend on the exposure parameterisation. DOSE-I is propofol mono-sedation, so
        `potency_units(ce_prop=...)` reduces to a monotone rescaling and P2 is a robustness arm rather
        than a second hypothesis. Reported either way (rule 59).

GATES

    G1  E122's, inherited: the pharmacology must be alive (out-of-bag rho > 0.10 at some rung). Without a
        working exposure model there is no residual for a direction term to explain, and the verdict is
        ABSENT rather than a null about hysteresis (rule 31 / rule 53).
    G2  BOTH DIRECTIONS MUST BE PRESENT IN THE SAME RECORDINGS. >= 25 recordings with at least 10 rising
        and 10 falling windows each. **A between-recording comparison of direction would be a comparison
        of cohorts, not of directions** (rule 32), so the coefficient is estimated within recording.
    G3  NEGATIVE CONTROL: a Gaussian column replaces the direction sign and must NOT return a coefficient
        excluding zero.

PLACEBO, and it gates the verdict (rule 34). **A rising/falling split is confounded with time-in-case**:
concentration rises early and falls late, so "falling" is very nearly "later", and any residual with a
within-case time trend produces a direction effect that has nothing to do with hysteresis. E98 was
withdrawn for exactly this shape and it earned rule 64. The placebo therefore RE-ASSIGNS the direction
label at a RANDOM index within each recording, preserving the number of rising and falling windows per
recording and their contiguity, and destroying only the correspondence with the concentration trajectory.
Compared against the placebo's DISTRIBUTION over 200 draws, never its mean (rule 37).

Rule 48: the primary's interval is read FIRST; if it includes zero the placebo is NOT INFORMATIVE and
says so rather than printing a pass.

VERDICT, wrong direction FIRST and by name (rule 37, and this is its sixth appearance in this project --
E125's first draft applied a placebo gate to only one branch two hours before this file was written):

    (a) coefficient excludes zero with the WRONG SIGN (falling windows LESS sedated than expected)
        -> ANTI-INERTIA. This excludes the null and REFUTES the hypothesis; it must not be filed as
        support. It would mean patients emerge FASTER than the pharmacology predicts, which is a real
        finding and a different one.
    (b) interval includes zero -> NO HYSTERESIS DETECTABLE. The effect-site model absorbs whatever
        direction dependence exists, which is consistent with Proekt and Kelz's first result and is NOT
        evidence that neural inertia is absent -- only that it is not separable here.
    (c) coefficient excludes zero with the PREDICTED sign AND beats the placebo -> HYSTERESIS BEYOND
        EQUILIBRATION. A direction dependence that a fitted effect-site basis could not absorb, measured
        against a state variable the model never saw. That is the identifiable version of neural inertia.

CALIBRATION, before the run: (b) ~55 %, (c) ~25 %, (a) ~20 %. (b) is favoured because the basis has eight
free rates fitted out of bag and Proekt and Kelz's point is precisely that such a basis can absorb a great
deal of direction dependence.

SCOPE. Procedural sedation with intermittent propofol boluses, one site, a five-point behavioural scale.
The scale is assessed by stimulating the patient, so the measurement itself perturbs arousal -- and it does
so more often during descent than during a stable plateau, which is a limitation this design cannot
remove and which the placebo does not address either. Stated now rather than after (rule 47).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
GOV = os.path.abspath(os.path.join(HERE, "..", "..", "..", "governance"))
OUT = os.path.join(RESULTS, "e126_hysteresis_residual.json")

RUNG = 2
MIN_PER_DIRECTION = 10
MIN_RECORDINGS = 25
REPS = 400
PLACEBO_DRAWS = 200
SEED = 126


def main(argv=None) -> int:
    import numpy as np
    from bsde.verifier.stats import cluster_bootstrap_ci, ridge_fit, spearman, _standardise

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--reps", type=int, default=REPS)
    ap.add_argument("--placebo-draws", type=int, default=PLACEBO_DRAWS)
    ap.add_argument("--register-only", action="store_true")
    a = ap.parse_args(argv)

    sys.path.insert(0, GOV)
    from registry_ledger import register                                   # noqa: E402
    try:
        register(
            "E126", "C",
            "Is there a hysteresis (neural inertia) that a fitted effect-site basis cannot absorb?",
            "DOSE-I",
            "coefficient of sign(dCe/dt) on the out-of-bag MOAA/S residual, within recording, "
            "PREDICTED NEGATIVE (falling = more sedated than the model expects)",
            ["G1 pharmacology alive (E122's gate)",
             "G2 >=25 recordings with >=10 rising AND >=10 falling windows -- within-recording only",
             "G3 gaussian negative control"],
            "re-assign the direction label at a RANDOM index within each recording, preserving counts "
            "and contiguity; 200 draws, compared against the DISTRIBUTION",
            os.path.relpath(__file__, os.path.join(HERE, "..", "..", "..", "..")),
            successor_of="E122",
            instrument_changed="a new QUESTION on E122's cohort: direction of concentration change, "
                               "which is identifiable only against a state measure the drug model never "
                               "saw (Proekt & Kelz 2021, PMID 33081972)")
        print("registered E126")
    except Exception as e:                                                 # noqa: BLE001
        print(f"registration: {e}")
    if a.register_only:
        return 0

    import e122_pharmacology_residual as E
    from bsde.pkpd.interaction import potency_units

    by, cands, off, cov, dose = E.load()
    kept, _ = E.build(by, cands, off, cov, dose)
    recs = sorted(kept)

    # ---- direction, from the MODELLED concentration ------------------------------------------------
    # The L2 basis is 8 columns; the concentration trajectory the direction refers to is the fitted
    # combination. Fitting it needs MOAA/S, so to avoid using the outcome to define the exposure's
    # direction we use the EQUALLY-WEIGHTED sum of the basis columns, which is a valid effect-site
    # signal (a positive combination of exponential kernels) and involves no outcome at all.
    for rec in recs:
        d = kept[rec]
        ce = d["pk"][RUNG].sum(axis=1)
        d["ce"] = ce
        g = np.gradient(ce, d["t"]) if ce.size > 2 else np.zeros_like(ce)
        d["dce"] = g
        d["dir"] = np.sign(g)

    ok_recs = [r for r in recs
               if int((kept[r]["dir"] > 0).sum()) >= MIN_PER_DIRECTION
               and int((kept[r]["dir"] < 0).sum()) >= MIN_PER_DIRECTION]
    gates = {"G2_recordings_both_directions": len(ok_recs),
             "G2_total_recordings": len(recs),
             "G2_pass": len(ok_recs) >= MIN_RECORDINGS}
    print(f"G2 {len(ok_recs)}/{len(recs)} recordings carry >= {MIN_PER_DIRECTION} windows in BOTH "
          f"directions  {'PASS' if gates['G2_pass'] else 'FAIL'}")
    if not gates["G2_pass"]:
        json.dump({"gates": gates, "verdict": "REFUSED: G2 -- direction does not vary within recordings, "
                                              "so any comparison would be between cohorts (rule 32)."},
                  open(a.out, "w"), indent=1)
        return 0

    X, y, s = E.stack(kept, ok_recs, lambda d: d["pk"][RUNG])
    rho = E.oob_rho(X, y, s, np.random.default_rng(SEED), reps=a.reps)
    gates["G1_oob_rho"] = rho
    gates["G1_pass"] = bool(np.isfinite(rho) and rho > 0.10)
    print(f"G1 pharmacology out-of-bag rho {rho:+.4f}  {'PASS' if gates['G1_pass'] else 'FAIL'}")
    if not gates["G1_pass"]:
        json.dump({"gates": gates,
                   "verdict": "ABSENT -- the exposure model does not predict MOAA/S here, so there is no "
                              "residual for a direction term to explain (rule 31)."},
                  open(a.out, "w"), indent=1)
        return 0

    def oob_residual(X, y, s, rng, reps):
        """Out-of-bag residual per row: mean over the resamples in which that row was NOT drawn."""
        uniq = np.unique(s)
        idx = {u: np.flatnonzero(s == u) for u in uniq}
        acc = np.zeros(y.size)
        cnt = np.zeros(y.size)
        for _ in range(reps):
            drawn = rng.choice(uniq, size=len(uniq), replace=True)
            ds = set(drawn.tolist())
            oob = [u for u in uniq if u not in ds]
            if len(oob) < 5:
                continue
            tr = np.concatenate([idx[u] for u in drawn])
            te = np.concatenate([idx[u] for u in oob])
            try:
                A, B = _standardise(X[tr], X[te])
                p = B @ ridge_fit(A, y[tr], 1.0)
            except Exception:                                             # noqa: BLE001
                continue
            acc[te] += (y[te] - p)
            cnt[te] += 1
        r = np.where(cnt > 0, acc / np.maximum(cnt, 1), np.nan)
        return r, cnt

    resid, cnt = oob_residual(X, y, s, np.random.default_rng(SEED + 1), a.reps)
    direction = np.concatenate([kept[r]["dir"] for r in ok_recs])
    good = np.isfinite(resid) & (cnt > 0) & (direction != 0)

    def within_coef(res, dirn, subj, mask):
        """Mean over recordings of (mean residual when falling) - (mean residual when rising).

        WITHIN RECORDING by construction: each recording contributes a difference of its own two means, so
        a recording that is entirely one direction contributes nothing and cannot leak a between-cohort
        contrast in (rule 32)."""
        vals, keys = [], []
        for u in np.unique(subj[mask]):
            m = mask & (subj == u)
            up, dn = m & (dirn > 0), m & (dirn < 0)
            if up.sum() < MIN_PER_DIRECTION or dn.sum() < MIN_PER_DIRECTION:
                continue
            vals.append(float(np.mean(res[dn]) - np.mean(res[up])))
            keys.append(u)
        return np.asarray(vals), np.asarray(keys)

    v, keys = within_coef(resid, direction, s, good)
    coef = float(np.mean(v)) if v.size else float("nan")
    lo, hi, _n = cluster_bootstrap_ci(lambda i: float(np.mean(v[i])), keys,
                                      np.random.default_rng(SEED + 2), reps=4000)
    print(f"P1 falling-minus-rising residual = {coef:+.4f} [{lo:+.4f}, {hi:+.4f}] over {v.size} recordings")

    # ---- P2: the same on the interaction model's potency units --------------------------------------
    for rec in ok_recs:
        d = kept[rec]
        d["dir_pot"] = np.sign(np.gradient(potency_units(ce_prop=d["ce"]), d["t"]))
    dir_pot = np.concatenate([kept[r]["dir_pot"] for r in ok_recs])
    v2, keys2 = within_coef(resid, dir_pot, s, np.isfinite(resid) & (cnt > 0) & (dir_pot != 0))
    coef2 = float(np.mean(v2)) if v2.size else float("nan")
    lo2, hi2, _ = cluster_bootstrap_ci(lambda i: float(np.mean(v2[i])), keys2,
                                       np.random.default_rng(SEED + 3), reps=4000)
    print(f"P2 same on potency units      = {coef2:+.4f} [{lo2:+.4f}, {hi2:+.4f}]")

    # ---- G3 negative control -------------------------------------------------------------------------
    rng = np.random.default_rng(SEED + 4)
    fake = np.sign(rng.normal(size=direction.size))
    v3, k3 = within_coef(resid, fake, s, np.isfinite(resid) & (cnt > 0) & (fake != 0))
    c3 = float(np.mean(v3)) if v3.size else float("nan")
    lo3, hi3, _ = cluster_bootstrap_ci(lambda i: float(np.mean(v3[i])), k3,
                                       np.random.default_rng(SEED + 5), reps=2000)
    gates["G3_negative_control"] = {"coef": c3, "lo": lo3, "hi": hi3}
    gates["G3_pass"] = bool(not (np.isfinite(lo3) and (lo3 > 0 or hi3 < 0)))
    print(f"G3 gaussian control          = {c3:+.4f} [{lo3:+.4f}, {hi3:+.4f}]  "
          f"{'PASS' if gates['G3_pass'] else 'FAIL'}")

    # ---- PLACEBO: random contiguous re-assignment of the direction label ------------------------------
    draws = []
    prng = np.random.default_rng(SEED + 6)
    for _ in range(a.placebo_draws):
        fake_dir = []
        for r in ok_recs:
            d = kept[r]["dir"]
            k = int(prng.integers(1, max(2, d.size)))
            fake_dir.append(np.roll(d, k))
        fd = np.concatenate(fake_dir)
        vv, kk = within_coef(resid, fd, s, np.isfinite(resid) & (cnt > 0) & (fd != 0))
        if vv.size:
            draws.append(float(np.mean(vv)))
    dr = np.asarray(draws, float)
    frac = float(np.mean(dr <= coef)) if dr.size and np.isfinite(coef) else float("nan")
    placebo = {"n": int(dr.size), "mean": float(dr.mean()) if dr.size else float("nan"),
               "p2.5": float(np.quantile(dr, .025)) if dr.size else float("nan"),
               "p97.5": float(np.quantile(dr, .975)) if dr.size else float("nan"),
               "frac_at_least_as_negative": frac}
    print(f"PLACEBO rolled direction: mean {placebo['mean']:+.4f} "
          f"[{placebo['p2.5']:+.4f}, {placebo['p97.5']:+.4f}]  frac<=real {frac:.3f}")

    beats = bool(np.isfinite(frac) and frac <= 0.05)
    if not np.isfinite(lo):
        verdict = "ABSENT -- the coefficient could not be estimated."
    elif lo > 0:
        verdict = (f"(a) ANTI-INERTIA -- {coef:+.4f} [{lo:+.4f}, {hi:+.4f}] excludes zero with the WRONG "
                   "sign: falling-concentration windows are LESS sedated than the pharmacology predicts, "
                   "not more. This excludes the null and REFUTES neural inertia rather than supporting "
                   "it, and must not be filed as support.")
    elif hi < 0 and beats:
        verdict = (f"(c) HYSTERESIS BEYOND EQUILIBRATION -- {coef:+.4f} [{lo:+.4f}, {hi:+.4f}], in the "
                   "predicted direction, and a randomly rolled direction label does not reproduce it "
                   f"(frac {frac:.3f}). A fitted 8-rate effect-site basis could not absorb this, and it "
                   "is measured against MOAA/S, which the model never saw -- the identifiable version of "
                   "neural inertia that Proekt & Kelz say requires exactly such a measurement.")
    elif hi < 0:
        verdict = (f"WITHDRAWN BY PLACEBO -- {coef:+.4f} [{lo:+.4f}, {hi:+.4f}] is in the predicted "
                   f"direction but a randomly rolled direction label reproduces it (frac {frac:.3f}). "
                   "That is rule 64: a rising/falling split is a time split in disguise unless a "
                   "random-split placebo says otherwise, and here it does not.")
    else:
        verdict = (f"(b) NO HYSTERESIS DETECTABLE -- {coef:+.4f} [{lo:+.4f}, {hi:+.4f}] includes zero. "
                   "The fitted effect-site basis absorbs whatever direction dependence exists, which is "
                   "consistent with Proekt & Kelz's first result and is NOT evidence that neural inertia "
                   "is absent -- only that it is not separable here. The placebo is NOT INFORMATIVE "
                   "(rule 48): there is no effect for a fake direction to fail to reproduce.")

    res = {"gates": gates,
           "P1": {"coef": coef, "lo": lo, "hi": hi, "n_recordings": int(v.size)},
           "P2_potency_units": {"coef": coef2, "lo": lo2, "hi": hi2, "n_recordings": int(v2.size)},
           "placebo": placebo, "verdict": verdict}
    json.dump(res, open(a.out, "w"), indent=1)
    print("\nVERDICT:", verdict)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
