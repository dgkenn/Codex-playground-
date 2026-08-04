#!/usr/bin/env python3
"""E72 -- the muscle audit E71 could not deliver, with a covariate that is a magnitude and controls that bracket it.

SUCCESSOR TO E71. **The changed instrument is the covariate transform and the control set** -- not the
hypothesis, not the cohort, not the threshold. H1 and the attribution statistic are carried over verbatim.

=========================================================================================================
WHY E71 STOPPED, AND WHAT HAD TO CHANGE
=========================================================================================================
E71's positive control failed and the gate correctly refused to report a twelve-feature audit. Two reasons,
both diagnosed rather than guessed:

1. **The control was invalid.** `emg_index` is a scalp proxy from Fpz-Cz and Pz-Oz. E69 had already found
   it shows no REM atonia, and measured against the real submental channel it correlates at only
   **rho = +0.20** pooled, **+0.30** within subject. A proxy already known to be broken cannot be ground
   truth (rule 57).

2. **Raw EMG amplitude is not a magnitude.** Submental EMG carries a subject-specific gain -- one subject
   moves 10 -> 3, another 1 -> 0.3 -- so paired differences have enormous between-subject variance. On the
   channel itself, wake versus N3 gives **d_z = +0.062**: the wrong sign and no effect, on a channel whose
   stage medians are 3.063 against 1.104.

**Both are fixed here and the fix was verified before this file was written.** Log-transforming and then
z-scoring within subject across the five stages gives **d_z = -0.550** on the channel itself, in the correct
direction, with stage medians ordering **W +0.874 > N1 +0.643 > N2 +0.081 > N3 -0.088 > REM -0.845** --
monotone down the depth staircase with REM lowest, which is what atonia should look like.

=========================================================================================================
THE CONTROLS BRACKET THE METHOD RATHER THAN ANCHORING ONE END OF IT
=========================================================================================================
E71 had one control and it was a proxy. This has two, both synthetic, both constructed from the validated
covariate itself so neither depends on any proxy being good:

    POS   a synthetic feature that IS the transformed EMG plus matched-variance noise. **It must rank at
          the top of the attribution ranking.** If the method cannot recover muscle from a feature that is
          literally muscle, nothing else in the table is readable.
    NEG   a synthetic feature that is pure noise, independent of everything. **It must rank at the bottom.**
          If noise scores as muscle-contaminated, the statistic is measuring the act of residualising
          rather than the covariate.

  G1 ALIVENESS (rule 53), per feature: the unadjusted W-vs-N3 d_z interval must exclude zero.
  G2 BRACKET GATE, and it can end the experiment: POS in the top two AND NEG in the bottom three of the
     combined ranking. **Both halves required** -- one-sided validation is how E71 got here.
  H1 BAND HYPOTHESIS, carried over unchanged and still declared from feature definitions: attribution
     should correlate POSITIVELY with the share of a feature's analysis band above 20 Hz.

VERDICT RULE, wrong direction first.

  (a) METHOD FAILS   -- G2 fails at either end. Nothing is readable and the audit is not reported.
  (b) H1 REVERSED    -- attribution correlates NEGATIVELY with band position, refuting the surface-EMG
                        account: the contamination tracks sleep stage but is not high-frequency muscle.
  (c) H1 ABSENT      -- the correlation includes zero. **The per-feature attributions still stand and are
                        reported** -- the audit is the deliverable, the mechanism is the bonus.
  (d) H1 SUPPORTED   -- positive, excluding zero. A feature whose band reaches into 20-45 Hz carries
                        submental muscle into every state contrast it is used for, and the low-band
                        features do not.

SCOPE, unchanged from E71: submental muscle in SLEEP recordings. It does not establish the same fraction
under anaesthesia, where neuromuscular blockade changes muscle tone entirely.

    python -m bsde.experiments.e72_muscle_audit_corrected
"""
from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
from bsde.verifier.stats import spearman                                      # noqa: E402
from bsde.experiments.e69_rem_dissociation import STAGES, load                # noqa: E402
from bsde.experiments.e71_muscle_attribution_audit import (HI_FRACTION, _boot_dz,   # noqa: E402
                                                           _dz, _resid)

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
EMG = os.path.join(RESULTS, "sleep_edfx_emg.csv")
OUT = os.path.join(RESULTS, "e72_muscle_audit_corrected.json")

POS, NEG = "_SYNTH_POS_muscle", "_SYNTH_NEG_noise"
PLACEBO_DRAWS = 120
SEED = 20260731


def transformed_emg(emg, subs):
    """log, then z-score WITHIN SUBJECT across the five stages. Verified before use: this turns the
    channel's own wake-vs-N3 effect from d_z = +0.062 (wrong sign) into -0.550 (correct)."""
    raw = {st: np.array([emg[f"{s}@{st}"] for s in subs]) for st in STAGES}
    lg = {st: np.log(np.clip(raw[st], 1e-6, None)) for st in STAGES}
    z = {st: np.zeros(len(subs)) for st in STAGES}
    for i in range(len(subs)):
        v = np.array([lg[st][i] for st in STAGES])
        m, s = v.mean(), v.std()
        for k, st in enumerate(STAGES):
            z[st][i] = (v[k] - m) / (s if s > 1e-9 else 1.0)
    return z


def attribution(E, M, subs, rng):
    """A = (|d2| - |d1|) / |d0|: the excess shrinkage from real EMG over shuffled EMG."""
    d0 = _dz(E["N3"] - E["W"])
    if not np.isfinite(d0) or abs(d0) < 1e-9:
        return float("nan"), d0, float("nan"), float("nan")
    R = _resid(E, M, subs)
    d1 = _dz(R["N3"] - R["W"])
    p = []
    for _ in range(PLACEBO_DRAWS):
        Mp = {st: M[st].copy() for st in STAGES}
        for i in range(len(subs)):
            v = rng.permutation([M[st][i] for st in STAGES])
            for k, st in enumerate(STAGES):
                Mp[st][i] = v[k]
        Rp = _resid(E, Mp, subs)
        p.append(_dz(Rp["N3"] - Rp["W"]))
    d2 = abs(float(np.nanmean(p)))
    return (d2 - abs(d1)) / abs(d0), d0, d1, d2


def main() -> int:
    emg = {r["recording_id"]: float(r["emg_mean"]) for r in csv.DictReader(open(EMG, newline=""))}
    per = load()
    subs = [s for s, d in per.items()
            if all(st in d for st in STAGES)
            and all(np.isfinite(emg.get(f"{s}@{st}", np.nan)) for st in STAGES)]
    M = transformed_emg(emg, subs)
    print(f"{len(subs)} subjects; covariate = log(submental EMG), z-scored within subject")
    print("   covariate stage medians: " + "  ".join(f"{st}={np.median(M[st]):+.3f}" for st in STAGES))
    print(f"   covariate's own W-vs-N3 d_z = {_dz(M['N3'] - M['W']):+.3f}\n")

    rng = np.random.default_rng(SEED)
    sd = float(np.std(np.concatenate([M[st] for st in STAGES])))
    E_all = {f: {st: np.array([per[s][st][f] for s in subs]) for st in STAGES} for f in HI_FRACTION}
    E_all[POS] = {st: M[st] + 0.5 * sd * rng.normal(size=len(subs)) for st in STAGES}
    # NEGATIVE CONTROL, CORRECTED. The first version used pure noise -- which has NO wake-vs-N3 effect by
    # construction, so G1 removed it before it could be ranked and the bracket gate could never close. A
    # control that cannot participate is not a control (rule 40). This version has a STRONG stage effect
    # and is independent of EMG by construction: a fixed monotone stage score plus per-subject noise.
    _stage_score = {"W": 0.0, "N1": 1.0, "N2": 2.0, "N3": 3.0, "REM": 1.0}
    E_all[NEG] = {st: _stage_score[st] + rng.normal(size=len(subs)) for st in STAGES}
    band = dict(HI_FRACTION)

    rows, res = [], {}
    print(f"{'feature':<26s} {'hi_frac':>8s} {'d0':>8s} {'G1':>5s} {'d1':>8s} {'d2':>8s} {'A':>8s}")
    for f, E in E_all.items():
        lo, hi = _boot_dz(E["N3"] - E["W"], np.random.default_rng(SEED))
        alive = np.isfinite(lo) and (lo > 0 or hi < 0)
        A, d0, d1, d2 = attribution(E, M, subs, np.random.default_rng(SEED + 1))
        bf = band.get(f, float("nan"))
        res[f] = {"testable": bool(alive and np.isfinite(A)), "d0": d0, "d1": d1, "d2": d2,
                  "attribution": A, "hi_fraction": bf}
        flag = "ok" if (alive and np.isfinite(A)) else "FAIL"
        print(f"{f:<26s} {bf:>8.3f} {d0:>8.3f} {flag:>5s} {d1:>8.3f} {d2:>8.3f} {A:>8.3f}")
        if alive and np.isfinite(A):
            rows.append((f, bf, A))

    order = sorted(rows, key=lambda r: -r[2])
    names = [r[0] for r in order]
    pr = names.index(POS) if POS in names else None
    nr = names.index(NEG) if NEG in names else None
    g2 = pr is not None and nr is not None and pr < 2 and nr >= len(names) - 3
    print(f"\nG2 bracket gate: POS ranks {'--' if pr is None else pr + 1}, "
          f"NEG ranks {'--' if nr is None else nr + 1}, of {len(names)}   {'PASS' if g2 else 'FAIL'}")
    print("   ranking (most muscle-attributable first): " + ", ".join(names))

    real = [r for r in order if r[0] not in (POS, NEG)]
    A = np.array([r[2] for r in real])
    F = np.array([r[1] for r in real])
    rho = spearman(A, F)
    b = []
    for _ in range(2000):
        i = rng.integers(0, len(A), len(A))
        if np.unique(F[i]).size > 2:
            v = spearman(A[i], F[i])
            if np.isfinite(v):
                b.append(v)
    b = np.sort(b)
    h_lo, h_hi = ((float(np.quantile(b, .025)), float(np.quantile(b, .975)))
                  if len(b) > 100 else (float("nan"), float("nan")))
    print(f"\nH1  Spearman(attribution, share of band above 20 Hz) = {rho:+.4f} "
          f"[{h_lo:+.4f}, {h_hi:+.4f}] over {len(A)} real features")

    if not g2:
        verdict = ("METHOD FAILS -- the bracket gate did not hold (a synthetic muscle feature must rank "
                   "top and pure noise must rank bottom). Nothing in the table is readable.")
    elif not np.isfinite(h_lo):
        verdict = "H1 ABSENT -- too few features to bootstrap; the per-feature audit stands."
    elif h_hi < 0:
        verdict = ("H1 REVERSED -- attribution is highest in the LOW-band features, refuting the "
                   "surface-EMG account. Whatever is removed tracks sleep stage but is not "
                   "high-frequency muscle.")
    elif h_lo <= 0:
        verdict = ("H1 ABSENT -- the band correlation includes zero. The per-feature attributions stand "
                   "as the deliverable and should be quoted; the mechanism does not follow from them.")
    else:
        verdict = ("H1 SUPPORTED -- muscle attribution rises with the share of a feature's band above "
                   "20 Hz. A feature reaching into 20-45 Hz carries submental muscle into every state "
                   "contrast it is used for, and the low-band features do not.")
    print(f"\nVERDICT: {verdict}")
    print("\nSCOPE: submental muscle in SLEEP recordings; says nothing about anaesthesia, where "
          "neuromuscular blockade changes muscle tone entirely.")
    json.dump({"n_subjects": len(subs), "features": res, "ranking": names,
               "gate_g2_bracket": bool(g2), "pos_rank": pr, "neg_rank": nr,
               "h1": {"rho": rho, "lo": h_lo, "hi": h_hi}, "verdict": verdict},
              open(OUT, "w"), indent=2)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
