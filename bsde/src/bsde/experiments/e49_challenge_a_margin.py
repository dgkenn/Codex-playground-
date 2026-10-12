#!/usr/bin/env python3
"""E49 -- Challenge A. What margin would an equivalence test need, and is one possible at all?

FEASIBILITY PROBE **AND** PRE-REGISTRATION, in that order (rule 41: run the probe BEFORE registering, so
the floors are set knowing the coverage). Nothing here touches a two-drug contrast, because no reachable
deposit has two agents in comparable patients -- that is the point.

=========================================================================================================
THE PROBLEM E49 EXISTS TO FIX
=========================================================================================================
Challenge A asks for a representation that predicts loss and recovery of responsiveness across
anaesthetics *while minimising drug-identification information*. Every attempt so far -- E21, E22, E25,
E29, E35, E36 -- asked "can a classifier tell the two agents apart?" and answered with an AUC.

**That statistic has the wrong null.** Failing to reject "the agents are distinguishable" is not evidence
that they are equivalent; with ten dexmedetomidine patients almost nothing is distinguishable. The
acceptance condition is an EQUIVALENCE claim and needs an equivalence test, which needs an indifference
margin declared in advance. Picking that margin by opinion would be indefensible, and picking it after
seeing the drug contrast would be the move `DISCOVERY_LOOP.md` §2 forbids.

**So derive it from data that contains no drug contrast at all.**

=========================================================================================================
THE IDEA: TWO STUDIES OF THE SAME DRUG DISAGREE BY SOME AMOUNT. THAT IS THE FLOOR.
=========================================================================================================
If two independent studies of the SAME anaesthetic, processed identically, disagree about the
awake-to-sedated displacement by delta, then two DIFFERENT anaesthetics must differ by more than delta
before the difference can be attributed to the drug rather than to the study. That is an empirical
indifference bound, measured on exactly the quantity the equivalence test would use, under a drug contrast
of exactly zero.

DEPOSITS, and what each can and cannot anchor -- checked, not assumed:

  chennu     20 subjects x 4 levels   PROPOFOL   plasma 0 / 447 / 900 / 290 ug/L
  ds005620   21 subjects              PROPOFOL   awake / sed / sed2 (repeated-awakening sedation study)
  ds004541    8 subjects              AGENT NOT RECORDED -- clinical GA; participants.tsv is entirely n/a

**chennu and ds005620 are the pair that sets the floor: same drug, different studies.** ds004541 carries
real loss of consciousness (`post_loc`) and so anchors the state-effect SCALE, but it cannot enter any
drug-specific statement because its agent is unknown and its demographics are absent.

A TRAP THAT WAS CAUGHT BEFORE IT WAS CODED. Chennu's level 4 is **RECOVERY, not the deepest level** --
plasma propofol runs 0 -> 447 -> 900 -> 290 and accuracy runs 37.9 -> 34.3 -> 26.9 -> 37.6 of 40. Taking
level 4 as "unresponsive" (the obvious reading of a 1-4 ordinal) would have contrasted awake against
recovered, produced a near-null displacement, and supported the conclusion that the state effect is tiny.
The deepest level is **3**. Verified from plasma concentration and behaviour, not from the label's ordering.

AND A LIMITATION THAT FALLS OUT OF THE SAME CHECK: at chennu's deepest level subjects still score 26.9/40,
so they are **sedated but responsive**. chennu and ds005620 are sedation studies, not unresponsiveness
studies. Only ds004541 crosses LOC. The floor is therefore measured on a SEDATION displacement and
generalises to an LOC displacement only by assumption -- stated here rather than discovered later.

=========================================================================================================
STATISTIC
=========================================================================================================
Per deposit, per feature, within subject:

    displacement_i = mean(feature | deep, subject i) - mean(feature | awake, subject i)
    Delta          = mean_i(displacement_i) / SD_i(mean(feature | awake, subject i))

i.e. the within-subject state shift expressed in units of that deposit's own BETWEEN-SUBJECT awake spread.
Dividing by an awake-only spread keeps the scale independent of the state effect it is scaling.

    delta_floor = |Delta(chennu) - Delta(ds005620)|          <- same drug, different study
    R           = mean(|Delta|) / delta_floor                <- resolvability

Subject-level bootstrap throughout; deposits are resampled independently and `delta_floor` is recomputed
inside each draw, so its CI carries both deposits' uncertainty.

=========================================================================================================
VERDICT RULE -- the failing case is written first and the wrong direction is named (rules 37, 49)
=========================================================================================================
Per feature:

  (a) NOT RESOLVABLE -- delta_floor's CI includes or exceeds mean(|Delta|). Two studies of the same drug
      disagree as much as the state effect itself, so a cross-deposit two-drug comparison cannot separate
      drug from deposit at any n. **This is a NEGATIVE result about Challenge A's feasibility and is the
      expected outcome** -- it would convert E36's qualitative structural limit into a number.
  (b) MARGINAL -- R between 1 and 3.
  (c) RESOLVABLE -- R > 3 with delta_floor's CI excluding mean(|Delta|).

REGISTERED MARGIN, fixed here for any future equivalence test:

    margin = max(delta_floor_upper_CI, mean(|Delta|) / 3)

and the future test MUST declare itself UNPOWERED rather than PASSED if `margin > mean(|Delta|)/2` -- a
margin that large makes equivalence declarable by construction, which is rule 48's degenerate case (a gate
cannot validate a claim when the claim is trivially satisfiable).

=========================================================================================================
WHAT THIS CANNOT SHOW
=========================================================================================================
* It does not test any drug contrast. It bounds what a drug contrast could ever detect.
* The three deposits' features come from EARLIER extraction scripts, not from `eeg_features_common.py`, so
  pipeline differences between them are not excluded. The mitigation is real but partial and should be
  stated precisely: a WITHIN-SUBJECT difference cancels any additive per-recording pipeline offset, but
  NOT a multiplicative or scale difference. Re-extracting all three through the shared path would remove
  the residual and is the obvious follow-up.
* chennu and ds005620 differ in more than study identity -- protocol, depth, montage, task. `delta_floor`
  is therefore an UPPER bound on same-drug disagreement, which makes the resolvability verdict
  conservative in the direction of declaring things not resolvable.
* Only the eight features common to all three deposits are used. `exponent_low`, the measure E43 and E46
  both selected, exists only in chennu and cannot be included -- a direct cost of the deposits having been
  extracted at different times.

    python -m bsde.experiments.e49_challenge_a_margin
"""
from __future__ import annotations

import csv
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e49_challenge_a_margin.json")

# (file, awake predicate, deep predicate, agent)
DEPOSITS = {
    "chennu": ("chennu_features_v3.csv",
               lambda r: r.get("meta_sedation_level") == "1.0",
               lambda r: r.get("meta_sedation_level") == "3.0",     # 3 is deepest; 4 is RECOVERY
               "propofol"),
    "ds005620": ("ds005620_features.csv",
                 lambda r: r.get("meta_task") == "awake",
                 lambda r: r.get("meta_task") in ("sed", "sed2"),
                 "propofol"),
    "ds004541": ("ds004541_v2.csv",
                 lambda r: r.get("meta_phase") == "awake_pre_drug",
                 lambda r: r.get("meta_phase") == "post_loc",
                 "unrecorded"),
}
SAME_DRUG_PAIR = ("chennu", "ds005620")
FEATURES = ("lempel_ziv", "whole_head_exponent", "relative_alpha_power", "relative_delta_power",
            "spectral_edge_95", "spectral_entropy", "uce_v1", "wpli_alpha")
MIN_SUBJECTS = 6
REPS = 20000
SEED = 20260731


def _f(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:                                                        # noqa: BLE001
        return None


def _load(name):
    fn, awake, deep, agent = DEPOSITS[name]
    with open(os.path.join(RESULTS, fn)) as fh:
        rows = [r for r in csv.DictReader(fh) if r.get("status", "ok") == "ok"]
    return rows, awake, deep, agent


def _per_subject(rows, awake, deep, feat):
    """(awake_mean, deep_mean) per subject, both present."""
    aw, dp = {}, {}
    for r in rows:
        v = _f(r.get(feat))
        if v is None:
            continue
        s = r.get("subject", "")
        if awake(r):
            aw.setdefault(s, []).append(v)
        elif deep(r):
            dp.setdefault(s, []).append(v)
    subs = sorted(set(aw) & set(dp))
    return (np.array([float(np.mean(aw[s])) for s in subs]),
            np.array([float(np.mean(dp[s])) for s in subs]), subs)


def _delta(a, d):
    """Within-subject displacement in units of the BETWEEN-SUBJECT awake spread."""
    if a.size < MIN_SUBJECTS:
        return float("nan")
    sd = float(np.std(a, ddof=1))
    if sd <= 0:
        return float("nan")
    return float(np.mean(d - a) / sd)


def main() -> int:
    data = {}
    for name in DEPOSITS:
        rows, awake, deep, agent = _load(name)
        data[name] = (rows, awake, deep, agent)

    print("=" * 100)
    print("E49 -- Challenge A: the equivalence margin, and whether an equivalence test is possible")
    print("=" * 100)
    for name, (rows, awake, deep, agent) in data.items():
        na = sum(1 for r in rows if awake(r))
        nd = sum(1 for r in rows if deep(r))
        print(f"   {name:10s} agent={agent:11s} rows={len(rows):4d}  awake={na:4d}  deep={nd:4d}")
    print(f"\n   same-drug pair for the floor: {SAME_DRUG_PAIR[0]} vs {SAME_DRUG_PAIR[1]} (both propofol)")
    print("   ds004541 anchors the state SCALE only -- its agent is not recorded.")

    rng = np.random.default_rng(SEED)
    results = {}
    print(f"\n   {'feature':22s} {'D(chennu)':>10s} {'D(5620)':>9s} {'D(4541)':>9s} "
          f"{'floor':>8s} {'floor 95%':>16s} {'R':>6s}  verdict")
    print("   " + "-" * 116)
    for feat in FEATURES:
        per = {}
        ok = True
        for name, (rows, awake, deep, _a) in data.items():
            a, d, subs = _per_subject(rows, awake, deep, feat)
            per[name] = (a, d, subs)
            if a.size < MIN_SUBJECTS:
                ok = False
        if not ok:
            print(f"   {feat:22s} -- too few paired subjects in at least one deposit; skipped")
            results[feat] = {"verdict": "SKIPPED (insufficient paired subjects)"}
            continue

        pt = {n: _delta(per[n][0], per[n][1]) for n in DEPOSITS}
        floor = abs(pt[SAME_DRUG_PAIR[0]] - pt[SAME_DRUG_PAIR[1]])
        mean_abs = float(np.mean([abs(pt[n]) for n in DEPOSITS if math.isfinite(pt[n])]))

        fl_draws, ma_draws = [], []
        for _ in range(REPS):
            dd = {}
            for n in DEPOSITS:
                a, d, _s = per[n]
                idx = rng.integers(0, a.size, a.size)
                dd[n] = _delta(a[idx], d[idx])
            if not all(math.isfinite(v) for v in dd.values()):
                continue
            fl_draws.append(abs(dd[SAME_DRUG_PAIR[0]] - dd[SAME_DRUG_PAIR[1]]))
            ma_draws.append(float(np.mean([abs(v) for v in dd.values()])))
        if len(fl_draws) < REPS // 2:
            results[feat] = {"verdict": "NOT INFORMATIVE (bootstrap degenerate)"}
            print(f"   {feat:22s} -- bootstrap degenerate")
            continue
        fl = np.sort(np.array(fl_draws))
        flo, fhi = float(np.quantile(fl, 0.025)), float(np.quantile(fl, 0.975))
        # fraction of resamples in which the same-drug floor reaches the state effect itself
        frac_swamped = float(np.mean(np.array(fl_draws) >= np.array(ma_draws)))
        R = mean_abs / floor if floor > 0 else float("inf")

        if frac_swamped > 0.05 or fhi >= mean_abs:
            v = "NOT RESOLVABLE (same-drug study disagreement reaches the state effect)"
        elif R > 3.0:
            v = "RESOLVABLE"
        else:
            v = "MARGINAL"
        margin = max(fhi, mean_abs / 3.0)
        unpowered = margin > mean_abs / 2.0
        results[feat] = {"delta": pt, "floor": floor, "floor_ci": [flo, fhi],
                         "mean_abs_delta": mean_abs, "R": R,
                         "frac_resamples_floor_ge_effect": frac_swamped,
                         "registered_margin": margin,
                         "future_test_unpowered_at_this_margin": bool(unpowered),
                         "verdict": v}
        print(f"   {feat:22s} {pt['chennu']:+10.3f} {pt['ds005620']:+9.3f} {pt['ds004541']:+9.3f} "
              f"{floor:8.3f} [{flo:6.3f},{fhi:6.3f}] {R:6.2f}  {v}")
        print(f"   {'':22s} registered margin {margin:.3f}"
              f"   future equivalence test would be {'UNPOWERED' if unpowered else 'powered'}"
              f"   P(floor >= effect) = {frac_swamped:.3f}")

    n_res = sum(1 for v in results.values() if v.get("verdict") == "RESOLVABLE")
    n_not = sum(1 for v in results.values() if str(v.get("verdict", "")).startswith("NOT RESOLVABLE"))
    print("\n" + "=" * 100)
    print(f"   RESOLVABLE {n_res} / NOT RESOLVABLE {n_not} / of {len(FEATURES)} features")
    print("   A feature is only usable for a cross-deposit Challenge A equivalence test if it is")
    print("   RESOLVABLE. Anything else means drug and deposit cannot be separated at any sample size.")
    os.makedirs(RESULTS, exist_ok=True)
    json.dump({"deposits": {k: {"agent": v[3]} for k, v in data.items()},
               "same_drug_pair": list(SAME_DRUG_PAIR), "features": results,
               "reps": REPS, "seed": SEED}, open(OUT, "w"), indent=2, default=str)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
