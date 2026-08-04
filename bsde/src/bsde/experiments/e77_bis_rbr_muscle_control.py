"""E77 -- Is `bis_rbr`'s arousal tracking submental muscle? The control Q35 owes, on a real EMG channel.

REGISTERED WHILE `sleep_edfx_bis_subparams.csv` WAS STILL EXTRACTING. What had been seen of that table when
this was written: its header, its stage counts (W 125, N1 125, N2 123, N3 124, REM 124 at that moment), and
one W row of one subject (`bis_rbr` 0.313466). **No wake-versus-sleep contrast, of any feature, had been
computed.** That single value is recorded here rather than glossed, because "no data was seen" would be a
tidier sentence and a false one.

--------------------------------------------------------------------------------------------------------
WHY
--------------------------------------------------------------------------------------------------------
QUEUE.md Q35 (exploratory) found that `bis_rbr` -- the relative beta ratio, implemented here from Rampil's
published description -- tracks a clinician's MOAA/S on DOSE-I at median within-recording rho **+0.5258**,
beating the deposit's own PE31 at **+0.4813** and its SEF95 at **+0.2507**. Q35 recorded the obvious
objection in the same breath: **`bis_rbr`'s numerator band is 30-47 Hz, which is where surface EMG lives.**

Q35's own muscle check was the best available and it is not enough. It partialled three SCALP-EEG muscle
proxies and found `bis_rbr` and PE31 attenuate by the same proportion. But E69 and E71 both established that
this project's scalp proxy fails its own premise -- `emg_index` shows NO REM atonia (REM 0.312 against N3
0.127) and correlates with a real submental channel at only rho +0.20 pooled / +0.30 within subject. **A
proxy that cannot see atonia cannot adjudicate a muscle question.** Q35 said so and named the fix: Sleep-EDFx
ships a real submental EMG channel, and `bis_rbr` had never been computed there.

--------------------------------------------------------------------------------------------------------
WHAT IS DIFFERENT FROM E71 AND E72, WHICH BOTH FAILED THEIR GATES
--------------------------------------------------------------------------------------------------------
E71 and E72 asked a **ranking** question across twelve or fourteen features, and both died on a rank-shaped
gate: E72's null control ranked 10 of 14 because four real features are themselves null, so a null control
necessarily lands among them. `CLAUDE.md` rule 58 forbids revising that gate a third time, and this
experiment does not: **it asks a magnitude question about ONE pre-declared feature, so its gate is a
separation, not a rank.**

Everything E72 verified is reused unchanged and is not re-litigated here:

* the covariate is `log(submental EMG)` z-scored WITHIN subject across the five stages, which turns the
  channel's own W-vs-N3 effect from d_z = +0.062 (wrong sign, raw amplitude carries a subject-specific
  gain) to **-0.550**, monotone down the depth staircase with REM lowest;
* attribution is `A = (|d2| - |d1|) / |d0|`, the excess shrinkage from real EMG over shuffled EMG, so the
  mechanical attenuation that ANY residualisation produces is subtracted rather than counted as muscle;
* the two synthetic controls (transformed EMG plus matched-variance noise; a stage-driven EMG-independent
  feature) scored **0.810** and **0.022** in E72.

--------------------------------------------------------------------------------------------------------
PRIMARY, and the pre-declared feature set
--------------------------------------------------------------------------------------------------------
    P1  A(`bis_rbr`) for the W-versus-N3 contrast, with a subject bootstrap interval.
    P2  A(`bis_sfs`), the other BIS subparameter with a fast/slow band structure.

`bis_bsr` and `bis_quazi` are the suppression subparameters. **PREDICTION WRITTEN NOW: both are identically
zero in physiological sleep, because there is no burst suppression there.** If they are, they are reported
INAPPLICABLE -- a constant has no contrast to attribute -- and they are NOT counted in the multiplicity.
Two tested features, Benjamini-Hochberg at q = 0.05, declared here rather than noted afterwards.

PREDICTION FOR P1, WRITTEN NOW: A(`bis_rbr`) > 0 and, given that its numerator band is entirely above
20 Hz, closer to `exponent_high`'s attribution than to `relative_alpha_power`'s. **This prediction is
against the interest of Q35's finding**, which is the point of running it.

--------------------------------------------------------------------------------------------------------
VERDICT RULE -- the wrong-direction case is the first branch, by name (rule 37, fourth occurrence)
--------------------------------------------------------------------------------------------------------
    (a) A's interval excludes 0 and A is NEGATIVE
            -> ANTI-MUSCLE. Real EMG adjustment removes LESS of the effect than a shuffled covariate does.
               That is not "muscle does not explain it": it is the feature moving OPPOSITE to muscle within
               subject, and it needs its own explanation before it is filed as reassurance.
    (b) A's interval includes 0
            -> NOT-ATTRIBUTED. No detectable muscle attribution. This is the outcome that DEFENDS Q35 --
               and it defends it only within this experiment's scope, below.
    (c) A's interval excludes 0 and A is POSITIVE
            -> MUSCLE-ATTRIBUTED, magnitude reported. A >= 0.5 means most of the wake/sleep effect is
               submental muscle, and `bis_rbr` must not be adopted as a Challenge C comparator on the
               strength of Q35 without an anaesthesia-side control.

--------------------------------------------------------------------------------------------------------
GATES, evaluated BEFORE the primary, each able to refuse it (rule 40)
--------------------------------------------------------------------------------------------------------
    G1  METHOD SEPARATES.  A(synthetic muscle) - A(synthetic null) >= 0.40, both constructed exactly as in
                           E72 and neither involving `bis_rbr`. E72 measured 0.810 and 0.022 on a
                           different feature table; this re-measures on THIS one, and it can fail.
    G2  THERE IS AN EFFECT TO ATTRIBUTE.  |d0| for the feature must have a bootstrap interval excluding 0.
                           Rule 48's logic in a new place: an attribution computed on a null effect divides
                           by a number that is not there, and would print as a result. A feature failing G2
                           is reported NO-EFFECT-TO-ATTRIBUTE, never as NOT-ATTRIBUTED.
    G3  COVERAGE.          >= 40 subjects carrying all five stages in BOTH the subparameter table and the
                           submental EMG table.

ANCHORS, declared now and DESCRIPTIVE ONLY (they set no threshold and gate nothing): `exponent_high`, whose
REM placement E70 found to be 58.7 % submental muscle against a 27.6 % mechanical placebo, and
`relative_alpha_power`, which E72 measured at -0.275. They are recomputed here so P1's number is read on a
scale with two known points on it rather than in the abstract.

--------------------------------------------------------------------------------------------------------
SCOPE LIMIT -- this is the sentence most likely to be dropped when the result is quoted
--------------------------------------------------------------------------------------------------------
This measures muscle attribution for a WAKE-versus-DEEP-SLEEP contrast in physiological sleep. Q35's
+0.5258 is a MOAA/S contrast under ANAESTHESIA. Muscle tone under anaesthesia is a different quantity --
neuromuscular blockade, and E22's finding that every VitalDB window at BIS >= 80 is facial EMG, both say so.
**A NOT-ATTRIBUTED verdict here removes one specific objection in one setting; it does not clear `bis_rbr`
on DOSE-I, and Q35's owed registered replication is owed either way.** Nothing here licenses calling any of
these measures a measure of consciousness.

    python -m bsde.experiments.e77_bis_rbr_muscle_control
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.experiments.e69_rem_dissociation import STAGES                      # noqa: E402
from bsde.experiments.e71_muscle_attribution_audit import _boot_dz, _dz, _resid   # noqa: E402
from bsde.experiments.e72_muscle_audit_corrected import (PLACEBO_DRAWS, attribution,   # noqa: E402
                                                          transformed_emg)

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
SUBPARAMS = os.path.join(RESULTS, "sleep_edfx_bis_subparams.csv")
FIVE_STAGE = os.path.join(RESULTS, "sleep_edfx_five_stage.csv")
EMG = os.path.join(RESULTS, "sleep_edfx_emg.csv")
OUT = os.path.join(RESULTS, "e77_bis_rbr_muscle_control.json")

TESTED = ["bis_rbr", "bis_sfs"]
SUPPRESSION = ["bis_bsr", "bis_quazi"]
ANCHORS = ["exponent_high", "relative_alpha_power"]
POS, NEG = "_SYNTH_POS_muscle", "_SYNTH_NEG_noise"
MIN_SUBJECTS = 40
G1_SEPARATION = 0.40
BOOT_REPS = 4000
BOOT_A_REPS = 200
BOOT_A_PLACEBO = 20
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def load_table(path, fields):
    per = defaultdict(dict)
    if not os.path.exists(path):
        return per
    for r in csv.DictReader(open(path, newline="")):
        rid = r.get("recording_id", "")
        if "@" not in rid:
            continue
        stage = rid.rsplit("@", 1)[1]
        if stage not in STAGES:
            continue
        per[r["subject"]][stage] = {f: _f(r.get(f, "")) for f in fields}
    return per


def _attribution(E, M, subs, rng, n_placebo):
    """E72's `attribution` with the placebo-draw count exposed.

    Byte-for-byte the same arithmetic; the only change is that the number of shuffled-covariate draws is a
    parameter rather than E72's module constant, because the subject bootstrap below calls this thousands
    of times and 120 inner draws per outer draw is not affordable. `main` asserts this reproduces E72's
    function exactly at n_placebo = PLACEBO_DRAWS before any result is computed (rule 23) -- a copied
    function that has silently drifted from its original is the failure this project has already paid for.
    """
    d0 = _dz(E["N3"] - E["W"])
    if not np.isfinite(d0) or abs(d0) < 1e-9:
        return float("nan"), d0, float("nan"), float("nan")
    R = _resid(E, M, subs)
    d1 = _dz(R["N3"] - R["W"])
    p = []
    for _ in range(n_placebo):
        Mp = {st: M[st].copy() for st in STAGES}
        for i in range(len(subs)):
            v = rng.permutation([M[st][i] for st in STAGES])
            for k, st in enumerate(STAGES):
                Mp[st][i] = v[k]
        Rp = _resid(E, Mp, subs)
        p.append(_dz(Rp["N3"] - Rp["W"]))
    d2 = abs(float(np.nanmean(p)))
    return (d2 - abs(d1)) / abs(d0), d0, d1, d2


def boot_A(E, M, subs, seed, reps=BOOT_A_REPS, n_placebo=BOOT_A_PLACEBO):
    """Subject bootstrap of the attribution. Resamples SUBJECTS, recomputing A on each resample."""
    rng = np.random.default_rng(seed)
    n = len(subs)
    vals = []
    for _ in range(reps):
        idx = rng.integers(0, n, n)
        Eb = {st: E[st][idx] for st in STAGES}
        Mb = {st: M[st][idx] for st in STAGES}
        a, _, _, _ = _attribution(Eb, Mb, [subs[i] for i in idx], rng, n_placebo)
        if np.isfinite(a):
            vals.append(a)
    if len(vals) < 50:
        return float("nan"), float("nan"), float("nan")
    v = np.sort(vals)
    return float(np.quantile(v, .025)), float(np.quantile(v, .975)), float(np.mean(np.asarray(v) <= 0))


def verdict(a, lo, hi):
    if not np.isfinite(a) or not np.isfinite(lo):
        return "NOT-COMPUTABLE"
    if lo < 0 and hi < 0:
        return "ANTI-MUSCLE"
    if lo > 0 and hi > 0:
        return "MUSCLE-ATTRIBUTED"
    return "NOT-ATTRIBUTED"


def main() -> int:
    res = {"gates": {}, "features": {}, "anchors": {}, "verdicts": {}}
    sub_tab = load_table(SUBPARAMS, TESTED + SUPPRESSION)
    five_tab = load_table(FIVE_STAGE, ANCHORS)
    if not os.path.exists(EMG):
        print("ABSENT: no submental EMG table"); return 2
    emg = {r["recording_id"]: _f(r["emg_mean"]) for r in csv.DictReader(open(EMG, newline=""))}

    subs = sorted(s for s, d in sub_tab.items()
                  if all(st in d for st in STAGES)
                  and all(f"{s}@{st}" in emg and np.isfinite(emg[f"{s}@{st}"]) for st in STAGES))
    res["gates"]["G3_subjects"] = len(subs)
    res["gates"]["G3_pass"] = bool(len(subs) >= MIN_SUBJECTS)
    print(f"G3 coverage  {len(subs)} subjects with all five stages in both tables   "
          f"{'PASS' if res['gates']['G3_pass'] else 'FAIL'}")
    if not res["gates"]["G3_pass"]:
        res["verdicts"]["overall"] = "GATE-FAILED"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    M = transformed_emg(emg, subs)
    rng = np.random.default_rng(SEED)

    # rule 23: the copied attribution must reproduce E72's, at E72's own draw count, before anything else
    probe = {st: M[st] + np.random.default_rng(99).normal(0, 1, len(subs)) for st in STAGES}
    a_ref, _, _, _ = attribution(probe, M, subs, np.random.default_rng(7))
    a_cpy, _, _, _ = _attribution(probe, M, subs, np.random.default_rng(7), PLACEBO_DRAWS)
    res["gates"]["G0_copy_matches_e72"] = float(abs(a_ref - a_cpy))
    if abs(a_ref - a_cpy) > 1e-12:
        print(f"G0 FAIL: the local attribution differs from E72's by {abs(a_ref - a_cpy):.3g}")
        res["verdicts"]["overall"] = "GATE-FAILED"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1
    print("G0 copy check  local attribution == E72's at 120 draws   PASS")

    # --- G1: the method must separate its own synthetic controls on THIS table -----------------------
    synth = {}
    sd = float(np.nanstd(np.concatenate([M[st] for st in STAGES])))
    synth[POS] = {st: M[st] + rng.normal(0, sd, len(subs)) for st in STAGES}
    stage_mean = {st: float(k) for k, st in enumerate(STAGES)}       # a clean depth staircase
    synth[NEG] = {st: stage_mean[st] + rng.normal(0, 1.0, len(subs)) for st in STAGES}
    a_pos, _, _, _ = attribution(synth[POS], M, subs, np.random.default_rng(SEED + 1))
    a_neg, _, _, _ = attribution(synth[NEG], M, subs, np.random.default_rng(SEED + 2))
    sep = a_pos - a_neg
    res["gates"].update({"G1_synth_muscle": a_pos, "G1_synth_null": a_neg,
                         "G1_separation": sep, "G1_pass": bool(sep >= G1_SEPARATION)})
    print(f"G1 separation  synth-muscle {a_pos:+.3f}  synth-null {a_neg:+.3f}  "
          f"separation {sep:+.3f}   {'PASS' if sep >= G1_SEPARATION else 'FAIL'}")

    # --- per-feature ---------------------------------------------------------------------------------
    def arm(name, table, tested):
        E = {st: np.array([table[s][st].get(name, np.nan) for s in subs]) for st in STAGES}
        finite = np.concatenate([E[st][np.isfinite(E[st])] for st in STAGES])
        if finite.size == 0 or float(np.nanstd(finite)) < 1e-12:
            print(f"    {name:22s} INAPPLICABLE (constant across every stage)")
            return {"status": "INAPPLICABLE"}
        d = E["N3"] - E["W"]
        d0 = _dz(d)
        lo0, hi0 = _boot_dz(d, np.random.default_rng(SEED + 3), reps=BOOT_REPS)
        g2 = bool(np.isfinite(lo0) and ((lo0 > 0 and hi0 > 0) or (lo0 < 0 and hi0 < 0)))
        if not g2:
            print(f"    {name:22s} d0 {d0:+.3f} [{lo0:+.3f}, {hi0:+.3f}]  "
                  f"NO-EFFECT-TO-ATTRIBUTE (G2 fails)")
            return {"status": "NO-EFFECT-TO-ATTRIBUTE", "d0": d0, "d0_lo": lo0, "d0_hi": hi0}
        a, _, d1, d2 = attribution(E, M, subs, np.random.default_rng(SEED + 4))
        lo, hi, frac_wrong = boot_A(E, M, subs, SEED + 5)
        v = verdict(a, lo, hi) if tested else None
        print(f"    {name:22s} d0 {d0:+.3f} [{lo0:+.3f}, {hi0:+.3f}]  "
              f"|d1| {abs(d1):.3f}  |d2| {d2:.3f}  A {a:+.3f} [{lo:+.3f}, {hi:+.3f}]"
              + (f"  {v}" if v else "   (anchor)"))
        return {"status": "OK", "d0": d0, "d0_lo": lo0, "d0_hi": hi0, "d1": d1, "d2": d2,
                "A": a, "A_lo": lo, "A_hi": hi, "A_frac_wrong_side": frac_wrong, "verdict": v}

    print("\nSUPPRESSION SUBPARAMETERS (predicted degenerate in physiological sleep)")
    for f in SUPPRESSION:
        res["features"][f] = arm(f, sub_tab, tested=False)

    print("\nANCHORS (descriptive; they gate nothing)")
    for f in ANCHORS:
        res["anchors"][f] = arm(f, five_tab, tested=False)

    print("\nTESTED")
    for f in TESTED:
        res["features"][f] = arm(f, sub_tab, tested=True)
        res["verdicts"][f] = res["features"][f].get("verdict")

    # --- Benjamini-Hochberg over the two tested features, on the bootstrap wrong-side fraction --------
    pvals = [(f, res["features"][f].get("A_frac_wrong_side")) for f in TESTED
             if res["features"][f].get("status") == "OK"]
    pvals = [(f, 2 * min(p, 1 - p)) for f, p in pvals if p is not None and np.isfinite(p)]
    m = len(pvals)
    if m:
        for rank, (f, p) in enumerate(sorted(pvals, key=lambda t: t[1]), 1):
            thr = 0.05 * rank / m
            res["features"][f]["bh_p"] = p
            res["features"][f]["bh_pass"] = bool(p <= thr)
            print(f"    BH  {f:22s} p {p:.4f}  threshold {thr:.4f}  "
                  f"{'survives' if p <= thr else 'does not survive'}")

    if not res["gates"]["G1_pass"]:
        print("\nG1 FAILED: the method did not separate its own controls on this table. Every attribution "
              "above is reported but NONE is licensed -- the verdict is ABSENT, not negative (rule 31).")
        res["verdicts"]["overall"] = "GATE-FAILED"
    else:
        res["verdicts"]["overall"] = res["verdicts"].get("bis_rbr", "NOT-COMPUTABLE")

    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
