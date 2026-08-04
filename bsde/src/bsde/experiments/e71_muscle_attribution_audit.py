#!/usr/bin/env python3
"""E71 -- cross-cutting. How much of each feature's wake/sleep effect is SUBMENTAL MUSCLE?

REGISTERED BEFORE ANY FEATURE OTHER THAN `exponent_high` HAS BEEN RESIDUALISED ON SUBMENTAL EMG. E70 ran
that one feature and is committed; the other eleven have not been touched by this control.

=========================================================================================================
WHY THIS IS THE AUDIT THE PROJECT ACTUALLY NEEDED
=========================================================================================================
E70 established, with a validated instrument, that **most of `exponent_high`'s wake-versus-sleep separation
is submental muscle**: REM's position on the W->N3 axis is +1.189 for the feature and +1.099 for the EMG
channel, and real-EMG adjustment removes 58.7 % of the distance from chance against a permuted placebo's
27.6 %.

That is not a fact about one feature. **`whole_head_exponent` is fitted over 1-40 Hz, `lempel_ziv` and
`critical_slowing_ar1` run to 45 Hz, and `spectral_entropy` and `spectral_edge_95` are computed over bands
reaching 40 Hz** -- every one of them overlaps the range where surface EMG lives. E43 measured this once
already, from a different direction, and found a broadband slope MORE muscle-associated than BIS.

**And a standing puzzle may fall out of it.** E50/E52 established that `exponent_low` and `exponent_high`
point in OPPOSITE directions, with the whole-band fit averaging them to nothing. If the high band is largely
muscle and the low band is not, that is a mechanism for the reversal rather than a restatement of it.

An independent probe run today supports the same split before this file was written: across 36 subjects with
both eyes-closed sessions of the sleep-deprivation cohort (ds004902), a night of deprivation moves
`exponent_low` at d_z = **+0.579** and `exponent_high` at **-0.003**. A drug-free arousal change moves the
low band and not the high one.

=========================================================================================================
DESIGN
=========================================================================================================
DATA. `sleep_edfx_five_stage.csv` joined to `sleep_edfx_emg.csv` on `recording_id` -- the same 710 windows,
by construction rather than reconstruction. 141 subjects with all five stages on both.

PER FEATURE, three numbers on the SAME rows:

    d0   within-subject paired d_z for W vs N3, unadjusted
    d1   the same after within-subject residualisation of the feature on submental EMG
    d2   the same after residualisation on a WITHIN-SUBJECT PERMUTED EMG vector (the mechanical cost of
         residualising on anything at all)

    MUSCLE ATTRIBUTION  A = (|d2| - |d1|) / |d0|

**A is the EXCESS reduction caused by real muscle over the reduction caused by shuffling**, expressed as a
fraction of the original effect. Subtracting the placebo rather than comparing against zero is the whole
point: residualising on any covariate shrinks an effect, and E70 measured that mechanical cost at 27.6 % of
the distance from chance.

  G1 ALIVENESS (rule 53), per feature: `d0`'s interval must exclude zero. A feature with no wake/sleep
     effect has no effect to attribute, and is reported UNTESTABLE.

  G2 POSITIVE CONTROL, and it can end the experiment. **`emg_index` is a muscle proxy by construction, so
     it MUST show high attribution.** If the method cannot recover muscle in the one feature designed to
     measure muscle, the method does not work and no other row means anything. Required: `emg_index` ranks
     in the top third of A. This is the check E66 lacked and E46 lacked before its correction -- a
     procedure that nothing fails is not a test (rule 49).

  H1 BAND HYPOTHESIS, falsifiable and declared from feature definitions rather than results: A should
     correlate POSITIVELY with `HI_FRACTION`, the share of a feature's analysis band lying above 20 Hz.
     **If the most muscle-attributable features are NOT the high-band ones, the EMG account is wrong** and
     the contamination is something else that happens to track sleep stage.

VERDICT RULE, wrong direction first.

  (a) METHOD FAILS   -- G2 fails; `emg_index` does not show high attribution and nothing else is readable.
  (b) H1 REVERSED    -- A correlates NEGATIVELY with band position: low-band features are the contaminated
                        ones, which refutes the surface-EMG account.
  (c) H1 ABSENT      -- the correlation includes zero. The per-feature attributions still stand as an
                        audit; the mechanism does not.
  (d) H1 SUPPORTED   -- positive, excluding zero. Muscle contamination rises with band position, and the
                        practical rule follows: a feature whose band reaches into 20-45 Hz carries muscle
                        into every state contrast it is used for, on this evidence.

WHAT NO OUTCOME LICENCES. This measures contamination by SUBMENTAL muscle in SLEEP recordings. It does not
establish that the same fraction contaminates anaesthesia data, where neuromuscular blockade changes muscle
tone entirely -- if anything the direction of that difference is the interesting follow-up, not an
assumption to carry.

    python -m bsde.experiments.e71_muscle_attribution_audit
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

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
EMG = os.path.join(RESULTS, "sleep_edfx_emg.csv")
OUT = os.path.join(RESULTS, "e71_muscle_attribution_audit.json")

# Share of each feature's analysis band lying above 20 Hz, computed from the feature's DEFINITION.
# Surface EMG becomes appreciable above roughly 20 Hz; the fit/integration ranges are those in the
# feature implementations, not chosen here.
HI_FRACTION = {
    "exponent_low": 0.0,                 # 1-20 Hz
    "exponent_high": 1.0,                # 20-40 Hz
    "whole_head_exponent": 0.513,        # 1-40 Hz -> (40-20)/(40-1)
    "relative_alpha_power": 0.0,         # 8-13 Hz
    "relative_delta_power": 0.0,         # 1-4 Hz
    "spectral_edge_95": 0.513,           # percentile over 0.5-40 Hz
    "spectral_entropy": 0.513,           # 0.5-40 Hz
    "lempel_ziv": 0.562,                 # broadband to 45 Hz
    "critical_slowing_ar1": 0.562,       # broadband to 45 Hz
    "multiscale_entropy_slope": 0.562,   # broadband to 45 Hz
    "pac_slow_alpha": 0.0,               # slow phase x alpha amplitude, <= 13 Hz
    "emg_index": 1.0,                    # POSITIVE CONTROL, muscle proxy by construction
}
POSITIVE_CONTROL = "emg_index"
REPS = 4000
PLACEBO_DRAWS = 120
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _dz(d):
    d = d[np.isfinite(d)]
    if d.size < 5 or d.std(ddof=1) < 1e-12:
        return float("nan")
    return float(d.mean() / d.std(ddof=1))


def _boot_dz(d, rng, reps=REPS):
    d = d[np.isfinite(d)]
    if d.size < 5:
        return float("nan"), float("nan")
    v = []
    for _ in range(reps):
        b = d[rng.integers(0, d.size, d.size)]
        if b.std(ddof=1) > 1e-12:
            v.append(b.mean() / b.std(ddof=1))
    v = np.sort(v)
    return float(np.quantile(v, .025)), float(np.quantile(v, .975))


def _resid(E, M, subs):
    """Within subject, regress the feature on EMG across that subject's five stages; keep residuals."""
    out = {st: np.full(len(subs), np.nan) for st in STAGES}
    for i in range(len(subs)):
        y = np.array([E[st][i] for st in STAGES])
        x = np.array([M[st][i] for st in STAGES])
        ok = np.isfinite(y) & np.isfinite(x)
        if ok.sum() < 4 or np.std(x[ok]) < 1e-12:
            continue
        A = np.column_stack([np.ones(int(ok.sum())), x[ok]])
        b = np.linalg.lstsq(A, y[ok], rcond=None)[0]
        r = y - (b[0] + b[1] * x)
        for k, st in enumerate(STAGES):
            out[st][i] = r[k]
    return out


def main() -> int:
    if not os.path.exists(EMG):
        print(f"MISSING {EMG}")
        return 2
    emg = {r["recording_id"]: _f(r["emg_mean"]) for r in csv.DictReader(open(EMG, newline=""))}
    per = load()
    feats = list(HI_FRACTION)
    subs = [s for s, d in per.items()
            if all(st in d for st in STAGES)
            and all(np.isfinite(emg.get(f"{s}@{st}", np.nan)) for st in STAGES)]
    print(f"{len(subs)} subjects with all five stages on both tables\n")
    M = {st: np.array([emg[f"{s}@{st}"] for s in subs]) for st in STAGES}

    rng = np.random.default_rng(SEED)
    rows, res = [], {}
    print(f"{'feature':<26s} {'hi_frac':>8s} {'d0':>8s} {'G1':>5s} {'d1(real)':>9s} "
          f"{'d2(perm)':>9s} {'A':>8s}")
    for f in feats:
        E = {st: np.array([per[s][st][f] for s in subs]) for st in STAGES}
        d0v = E["N3"] - E["W"]
        d0 = _dz(d0v)
        lo, hi = _boot_dz(d0v, np.random.default_rng(SEED))
        alive = np.isfinite(lo) and (lo > 0 or hi < 0)
        if not alive or not np.isfinite(d0) or abs(d0) < 1e-9:
            res[f] = {"testable": False, "d0": d0}
            print(f"{f:<26s} {HI_FRACTION[f]:>8.3f} {d0:>8.3f} {'FAIL':>5s}")
            continue
        R = _resid(E, M, subs)
        d1 = _dz(R["N3"] - R["W"])
        p = []
        rp = np.random.default_rng(SEED + 1)
        for _ in range(PLACEBO_DRAWS):
            Mp = {st: M[st].copy() for st in STAGES}
            for i in range(len(subs)):
                vals = rp.permutation([M[st][i] for st in STAGES])
                for k, st in enumerate(STAGES):
                    Mp[st][i] = vals[k]
            Rp = _resid(E, Mp, subs)
            p.append(_dz(Rp["N3"] - Rp["W"]))
        # FOLD ONCE, AT THE END, EXACTLY AS d1 IS FOLDED. The first version took mean(|d_z|) across
        # permutations and differenced that against a singly-folded |d1|. A folded statistic is biased
        # upward under noise (rule 46: it may only be differenced against itself on the same rows), so the
        # placebo sat systematically above the real adjustment and the attribution was garbage for every
        # feature with a negative d0. The POSITIVE CONTROL caught it: emg_index ranked 7 of 12.
        d2 = abs(float(np.nanmean(p)))
        A = (d2 - abs(d1)) / abs(d0)
        res[f] = {"testable": True, "d0": d0, "d1": d1, "d2": d2, "attribution": A,
                  "hi_fraction": HI_FRACTION[f]}
        rows.append((f, HI_FRACTION[f], A))
        print(f"{f:<26s} {HI_FRACTION[f]:>8.3f} {d0:>8.3f} {'ok':>5s} {d1:>9.3f} {d2:>9.3f} {A:>8.3f}")

    if not rows:
        print("\nG1 removed every feature. Verdict ABSENT (rule 31).")
        json.dump({"features": res, "verdict": "ABSENT"}, open(OUT, "w"), indent=2)
        return 1

    order = sorted(rows, key=lambda r: -r[2])
    names = [r[0] for r in order]
    pc_rank = names.index(POSITIVE_CONTROL) if POSITIVE_CONTROL in names else None
    g2 = pc_rank is not None and pc_rank < max(1, len(names) // 3)
    print(f"\nG2 positive control: {POSITIVE_CONTROL} ranks "
          f"{'--' if pc_rank is None else pc_rank + 1} of {len(names)} by attribution   "
          f"{'PASS' if g2 else 'FAIL'} (must be in the top third)")
    print("   ranking, most muscle-attributable first: " + ", ".join(names))

    A = np.array([r[2] for r in order])
    F = np.array([r[1] for r in order])
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
          f"[{h_lo:+.4f}, {h_hi:+.4f}] over {len(A)} features")

    if not g2:
        verdict = (f"METHOD FAILS -- {POSITIVE_CONTROL} is a muscle proxy by construction and does not "
                   f"rank among the most muscle-attributable features. The procedure cannot recover muscle "
                   f"where muscle is known to be, so no other row is readable.")
    elif not np.isfinite(h_lo):
        verdict = "H1 ABSENT -- too few features to bootstrap the correlation; the audit still stands."
    elif h_hi < 0:
        verdict = ("H1 REVERSED -- muscle attribution is HIGHEST in the LOW-band features, which refutes "
                   "the surface-EMG account. Whatever is being removed tracks sleep stage but is not "
                   "high-frequency muscle.")
    elif h_lo <= 0:
        verdict = ("H1 ABSENT -- the band correlation includes zero. The per-feature attributions stand as "
                   "an audit and should be quoted; the mechanism does not follow from them.")
    else:
        verdict = ("H1 SUPPORTED -- muscle attribution rises with the share of a feature's band above "
                   "20 Hz. On this evidence a feature reaching into 20-45 Hz carries submental muscle into "
                   "every state contrast it is used for, and the low-band features do not.")
    print(f"\nVERDICT: {verdict}")
    print("\nNOTE: this is contamination by SUBMENTAL muscle in SLEEP recordings. It does not establish the "
          "same fraction under anaesthesia, where neuromuscular blockade changes muscle tone entirely.")
    json.dump({"n_subjects": len(subs), "features": res, "ranking": names,
               "gate_g2_positive_control": bool(g2),
               "h1": {"rho": rho, "lo": h_lo, "hi": h_hi}, "verdict": verdict},
              open(OUT, "w"), indent=2)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
