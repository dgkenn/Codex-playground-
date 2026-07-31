#!/usr/bin/env python3
"""E70 -- the control E69 named and could not run: is `exponent_high`'s awake/asleep boundary just MUSCLE?

REGISTERED BEFORE ANY EMG VALUE HAS BEEN JOINED TO ANY EEG FEATURE. The submental extraction was piloted on
five windows to confirm the channel decodes ("EMG submental", 1 Hz, 120 samples per window) and those five
values were seen. Nothing has been correlated, residualised or compared.

=========================================================================================================
WHAT E69 LEFT OPEN, IN ITS OWN WORDS
=========================================================================================================
E69 found `exponent_high` alone places REM with sleep rather than wake, then narrowed the claim on its own
stage medians: **W +0.070, N1 +2.104, N2 +1.985, N3 +1.599, REM +2.089.** Wake is the outlier and every
sleep stage sits together, so the feature marks an AWAKE/ASLEEP boundary rather than depth.

It also named the alternative it could not rule out. `exponent_high` is fitted over **20-40 Hz**, where
surface EMG lives, and E43 measured that a broadband slope through that band is *more* muscle-associated
than BIS. Wake carries more muscle tone than any sleep stage. **A flatter 20-40 Hz slope at wake is exactly
what muscle would produce.**

E69's subject-level check against `emg_index` returned rho = +0.068 and does NOT settle this, because
`emg_index` is computed from Fpz-Cz and Pz-Oz and those channels showed no REM atonia at all (REM 0.312
against N3 0.127). **A proxy that fails its own premise cannot exonerate anything** (rule 50: measure the
difference with the suspected cause held constant, using a control of the right shape).

Sleep-EDFx PSG ships a real **submental** EMG channel. `scripts/extract_sleep_emg.py` reads it on exactly
the windows in `sleep_edfx_five_stage_worklist.json`, so the join is by construction rather than by
reconstruction.

=========================================================================================================
DESIGN
=========================================================================================================
  G1 INSTRUMENT GATE, evaluated FIRST and able to end the experiment. **The EMG channel must behave like a
  muscle channel before it can be used to explain anything.** Required: wake EMG exceeds sleep EMG, and REM
  EMG is at or below N3's (atonia). If submental EMG does NOT show atonia in these recordings, it is not
  measuring muscle tone as understood, and no conclusion about muscle may be drawn either way -- the verdict
  is ABSENT, not "muscle exonerated".

  S1 ORDERING       where does REM sit on the W->N3 axis for EMG, against `exponent_high`'s **1.189**? If
                    muscle drives the feature, the two positions should agree. This is a direct comparison
                    with no model in it and it is reported whatever the primary says.

  PRIMARY           `exponent_high` residualised on submental EMG **within subject**, then E69's statistic
                    recomputed: the fraction of subjects for whom REM lies nearer W than N3.
                    **PREDICTED UNDER THE MUSCLE HYPOTHESIS: the fraction returns toward 0.5.** If it stays
                    near E69's 0.113, muscle does not account for the effect.

  P1 PLACEBO        the same residualisation against a WITHIN-SUBJECT PERMUTED EMG vector. Residualising on
                    ANY covariate removes variance, so a shift toward 0.5 means nothing unless the real EMG
                    shifts it further than a shuffled one does. **A comparison against the real effect,
                    never a threshold** (rule 34).

  S2 WAKE/ASLEEP    the same before/after adjustment for the wake-versus-all-sleep contrast, which is what
                    E69's stage medians say the feature actually marks.

VERDICT RULE, wrong direction first.

  (a) MUSCLE EXPLAINS IT -- the real-EMG adjustment moves the fraction toward 0.5 and does so further than
                            the permuted placebo. `exponent_high`'s awake/asleep boundary is muscle tone
                            read through a 20-40 Hz slope, and E69's one departing feature departs for a
                            peripheral reason. **This is the outcome that would retire the finding.**
  (b) ABSENT             -- G1 failed: the channel does not behave like muscle, so nothing about muscle can
                            be concluded.
  (c) NOT INFORMATIVE    -- real and permuted adjustment move the fraction equally; the shift is the
                            mechanical cost of residualising, not muscle.
  (d) SURVIVES           -- the fraction stays away from 0.5 after real-EMG adjustment. `exponent_high`
                            marks awake-versus-asleep for a reason that is not submental muscle tone.
                            **Still not a consciousness claim**: it would remain a boundary between two
                            scorer-defined state groups, now with one specific confound excluded.

    python -m bsde.experiments.e70_rem_emg_control
"""
from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
from bsde.experiments.e69_rem_dissociation import STAGES, load                # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
EMG = os.path.join(RESULTS, "sleep_edfx_emg.csv")
OUT = os.path.join(RESULTS, "e70_rem_emg_control.json")

FEATURE = "exponent_high"
REPS = 4000
PLACEBO_DRAWS = 200
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _boot_mean(v, rng, reps=REPS):
    v = np.asarray(v, float)
    if v.size < 5:
        return float("nan"), float("nan")
    d = np.sort([v[rng.integers(0, v.size, v.size)].mean() for _ in range(reps)])
    return float(np.quantile(d, .025)), float(np.quantile(d, .975))


def _frac_near_w(vals):
    """vals: dict stage -> array over subjects. Fraction with REM nearer W than N3."""
    W, N3, RE = vals["W"], vals["N3"], vals["REM"]
    ok = np.isfinite(W) & np.isfinite(N3) & np.isfinite(RE)
    return (np.abs(RE - W) < np.abs(RE - N3))[ok].astype(float)


def main() -> int:
    if not os.path.exists(EMG):
        print(f"MISSING {EMG} -- run scripts/extract_sleep_emg.py first")
        return 2
    emg = {r["recording_id"]: _f(r["emg_mean"]) for r in csv.DictReader(open(EMG, newline=""))}
    per = load()
    subs = [s for s, d in per.items()
            if all(st in d for st in STAGES)
            and all(np.isfinite(emg.get(f"{s}@{st}", np.nan)) for st in STAGES)
            and all(np.isfinite(d[st][FEATURE]) for st in STAGES)]
    print(f"{len(subs)} subjects with all five stages on BOTH the EEG feature and submental EMG")
    if len(subs) < 30:
        print("too few joined subjects; verdict ABSENT (rule 31)")
        json.dump({"n_subjects": len(subs), "verdict": "ABSENT -- join too small"},
                  open(OUT, "w"), indent=2)
        return 1

    E = {st: np.array([per[s][st][FEATURE] for s in subs]) for st in STAGES}
    M = {st: np.array([emg[f"{s}@{st}"] for s in subs]) for st in STAGES}

    # G1: does the channel behave like muscle?
    med = {st: float(np.median(M[st])) for st in STAGES}
    wake_gt_sleep = all(med["W"] > med[st] for st in ("N1", "N2", "N3", "REM"))
    rem_atonia = med["REM"] <= med["N3"]
    g1 = bool(wake_gt_sleep and rem_atonia)
    print("\nG1 instrument gate -- submental EMG medians by stage:")
    print("   " + "  ".join(f"{st}={med[st]:.4g}" for st in STAGES))
    print(f"   wake > every sleep stage: {wake_gt_sleep}   REM <= N3 (atonia): {rem_atonia}   "
          f"G1 {'PASS' if g1 else 'FAIL'}")

    res = {"n_subjects": len(subs), "emg_stage_medians": med, "gate_g1": g1}
    if not g1:
        verdict = ("ABSENT -- the submental channel does not behave like a muscle channel in these "
                   "recordings (wake is not above every sleep stage, or REM shows no atonia). It cannot "
                   "be used to explain or exonerate anything, and E69's finding is neither supported nor "
                   "retired by this experiment.")
        print(f"\nVERDICT: {verdict}")
        res["verdict"] = verdict
        json.dump(res, open(OUT, "w"), indent=2)
        return 0

    # S1: REM position on the W->N3 axis, EMG against the feature.
    def pos(d):
        g = np.abs(d["N3"] - d["W"]) > 1e-9
        return float(np.median(((d["REM"] - d["W"]) / (d["N3"] - d["W"]))[g]))
    print(f"\nS1 REM position on the W->N3 axis:  {FEATURE} = {pos(E):+.3f}   submental EMG = {pos(M):+.3f}")

    rng = np.random.default_rng(SEED)
    raw = _frac_near_w(E)
    rlo, rhi = _boot_mean(raw, np.random.default_rng(SEED))
    print(f"\nBEFORE adjustment: frac REM nearer W = {raw.mean():.3f} [{rlo:.3f}, {rhi:.3f}]")

    def residualise(Mst):
        """Within subject, regress the feature on EMG across that subject's five stages; keep residuals."""
        out = {st: np.full(len(subs), np.nan) for st in STAGES}
        for i in range(len(subs)):
            y = np.array([E[st][i] for st in STAGES])
            x = np.array([Mst[st][i] for st in STAGES])
            ok = np.isfinite(y) & np.isfinite(x)
            if ok.sum() < 4 or np.std(x[ok]) < 1e-12:
                continue
            A = np.column_stack([np.ones(ok.sum()), x[ok]])
            b = np.linalg.lstsq(A, y[ok], rcond=None)[0]
            r = y - (b[0] + b[1] * x)
            for k, st in enumerate(STAGES):
                out[st][i] = r[k]
        return out

    adj = _frac_near_w(residualise(M))
    alo, ahi = _boot_mean(adj, np.random.default_rng(SEED + 1))
    print(f"AFTER real-EMG adjustment:          frac = {adj.mean():.3f} [{alo:.3f}, {ahi:.3f}]")

    rp = np.random.default_rng(SEED + 2)
    plac = []
    for _ in range(PLACEBO_DRAWS):
        Mp = {st: M[st].copy() for st in STAGES}
        for i in range(len(subs)):
            vals = rp.permutation([M[st][i] for st in STAGES])
            for k, st in enumerate(STAGES):
                Mp[st][i] = vals[k]
        plac.append(_frac_near_w(residualise(Mp)).mean())
    plac_mean = float(np.mean(plac))
    print(f"P1 PLACEBO permuted-EMG adjustment: frac = {plac_mean:.3f} ({PLACEBO_DRAWS} draws)")

    d_real = abs(adj.mean() - 0.5)
    d_plac = abs(plac_mean - 0.5)
    d_raw = abs(raw.mean() - 0.5)
    print(f"\ndistance from chance:  before {d_raw:.3f}   real-adjusted {d_real:.3f}   "
          f"placebo-adjusted {d_plac:.3f}")

    res.update({"rem_position_feature": pos(E), "rem_position_emg": pos(M),
                "frac_before": float(raw.mean()), "frac_before_ci": [rlo, rhi],
                "frac_after_real": float(adj.mean()), "frac_after_real_ci": [alo, ahi],
                "frac_after_placebo": plac_mean})
    if d_real >= d_plac:
        verdict = (f"SURVIVES -- adjusting for real submental EMG leaves the effect at least as far from "
                   f"chance as a permuted-EMG adjustment does ({d_real:.3f} vs {d_plac:.3f}). "
                   f"{FEATURE}'s awake-versus-asleep boundary is not submental muscle tone. Still NOT a "
                   f"consciousness claim: it remains a boundary between scorer-defined state groups, now "
                   f"with one specific confound excluded.")
    elif d_real < 0.5 * d_plac:
        verdict = (f"MUSCLE EXPLAINS IT -- real-EMG adjustment collapses the effect toward chance "
                   f"({d_real:.3f}) far beyond the permuted placebo ({d_plac:.3f}). {FEATURE} reads muscle "
                   f"tone through a 20-40 Hz slope, and E69's one departing feature departs for a "
                   f"peripheral reason. The finding is retired.")
    else:
        verdict = (f"NOT INFORMATIVE -- real and permuted adjustment move the statistic comparably "
                   f"({d_real:.3f} vs {d_plac:.3f}), so the shift is the mechanical cost of residualising "
                   f"rather than muscle.")
    print(f"\nVERDICT: {verdict}")
    res["verdict"] = verdict
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
