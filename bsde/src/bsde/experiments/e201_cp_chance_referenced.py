#!/usr/bin/env python3
"""E201 — E199's test with the aliveness gate the deposit itself supplies.

REGISTERED WHILE THE CHANCE-RUN EXTRACTION IS STILL RUNNING; no chance-run value has been inspected.

=========================================================================================================
TWO GATE FAILURES ON THE SAME STATISTIC, AND WHY THE STATISTIC IS THE SUSPECT
=========================================================================================================
E192 (session 1) and E199 (each subject's final session) both returned NOT INTERPRETABLE at the same gate:

                              pooled vel_alignment   sign-flip p95   subjects positive   median mean_dist
    E192  Se01                      **−0.0738**         +0.0416          6 of 28              0.4831
    E199  final session             **−0.0371**         +0.0469         11 of 28              0.4824

The cohort change did almost nothing, and it removed the one confound it was aimed at — the final session
carries all six decoders (AR/EG/PN and CL/DL/TL, 280 trials each) where Se01 carried only the traditional
AR decoder for the Main subjects. Everything else passed both times: 1,680 trials, 28 subjects, ~1,230
matched adjacent pairs, the outcome graded within run, and a pairing balanced to +0.0000 with the trial
index at p = 0.985.

**`vel_alignment` is the cosine between cursor velocity and the CURRENT direction to the target.** In
continuous pursuit the target drifts continuously and a motor-imagery decoder carries a lag of order a
second, so a subject who is tracking well aims where the target *was*. The statistic conflates control with
lag and can sit at or below zero while tracking is far better than chance. It is the wrong instrument for
aliveness, and rule 55 is the relevant one: a gate must be sensitive to the thing it claims to measure.

=========================================================================================================
THE DEPOSIT SHIPS THE RIGHT REFERENCE, AND A REGEX HAD EXCLUDED IT
=========================================================================================================
The README states that each session contains a 13th run **"used to estimate a chance level"**. Those
members are named `S##_Se##_Chance_R##.mat`, and the extractor's member pattern required exactly two
UPPERCASE letters for the decoder code — so every one was silently dropped. That is catalogue rule 61's
shape: a structured identifier matched by a pattern never checked against the actual namespace.

    **G2'  ALIVENESS AGAINST THE STUDY'S OWN CHANCE RUN.** For each subject, the mean cursor-target
          distance over the real runs of that session must be BELOW the mean over that session's Chance
          run. The gate is the paired across-subject comparison against a sign-flip null.

This is a measured reference produced by the data's authors for exactly this purpose, not a statistic I
chose, and it is immune to the lag objection because it compares like with like — the same subject, the
same session, the same task, the same 60 s trials, differing only in whether the cursor is under the
subject's control.

=========================================================================================================
WHAT IS AND IS NOT CHANGED
=========================================================================================================
Changed: **the aliveness gate only.** Nothing else — the cohort is E199's final session, the primary is
`mean_dist`, the primary candidate is `mu_mean`, the direction is fixed in advance BELOW 0.5, the matched
adjacent-trial pairing, the four scorings, the BH correction, the floors and every verdict branch are
E199's, reached through E192's module so there is a single implementation.

**This is a gate replacement after two failures of the old gate, and that has to be justified rather than
asserted.** The justification is that the objection to `vel_alignment` is *a priori* — it follows from the
task's structure and the decoder's lag, not from the direction the gate failed in — and that the
replacement is not a looser threshold but a **different and better-founded measurement**, supplied by the
deposit. If a reader rejects that, the correct reading is E199's: this deposit cannot test E181.

=========================================================================================================
VERDICT — WRONG-DIRECTION CASES FIRST (rule 37)
=========================================================================================================
  (1) NOT INTERPRETABLE   G1, G2', G3 or G4 fails. If G2' fails, subjects do not track better than the
                          study's own chance run and the deposit genuinely cannot test E181.
  (2) REVERSED            `mu_mean` clears its floor with an interval ABOVE 0.5 — refutes E181.
  (3) ABSENT ABOVE FLOOR  `mu_mean` does not clear the measured floor.
  (4) FRAGILE             clears on the primary scoring but at least two of the three other scorings sit
                          the other side of 0.5.
  (5) REPLICATED          clears in E181's direction and the other scorings agree in sign.

**REGISTERED PREDICTION: G2' PASSES and the primary is (3) ABSENT ABOVE FLOOR.** The aliveness prediction
is a real one and could be wrong — the median real-run distance is 0.4824, and if the chance runs sit near
0.48 as well then the paradigm is not producing control in this deposit at all. The primary prediction is
restated rather than inherited, for the same reason as in E199: two of the three prior external or
held-out tests of a pre-cue alpha effect returned absent.

    python bsde/src/bsde/experiments/e201_cp_chance_referenced.py
"""

from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, HERE)

import e172_matched_pair_trial_responsiveness as E172                          # noqa: E402
import e192_continuous_pursuit_graded_replication as E192                      # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
CHANCE = [os.path.join(RESULTS, f"cp_chance.s{k}.csv") for k in range(4)] + \
         [os.path.join(RESULTS, "cp_chance.csv")]
REPS = 2000
SEED = 20260802


def chance_by_subject():
    """Mean cursor-target distance in each subject's Chance run, keyed by (subject, session)."""
    out = {}
    seen = set()
    for p in CHANCE:
        if not os.path.exists(p):
            continue
        with open(p, newline="") as fh:
            for r in csv.DictReader(fh):
                key = (r["subject"], r["session"], r["run"], r["decoder"], r["trial"])
                if key in seen:
                    continue
                seen.add(key)
                try:
                    v = float(r["mean_dist"])
                except (TypeError, ValueError):
                    continue
                if np.isfinite(v):
                    out.setdefault((r["subject"], r["session"]), []).append(v)
    return {k: float(np.mean(v)) for k, v in out.items() if v}


def real_by_subject():
    out, seen = {}, set()
    for p in E192.TABLES:
        if not os.path.exists(p):
            continue
        with open(p, newline="") as fh:
            for r in csv.DictReader(fh):
                key = (r["subject"], r["session"], r["run"], r["decoder"], r["trial"])
                if key in seen:
                    continue
                seen.add(key)
                try:
                    v = float(r["mean_dist"])
                except (TypeError, ValueError):
                    continue
                if np.isfinite(v):
                    out.setdefault((r["subject"], r["session"]), []).append(v)
    return {k: float(np.mean(v)) for k, v in out.items() if v}


def aliveness():
    """G2': per subject, real-run mean distance minus that session's Chance-run mean distance.

    Negative is better tracking. The gate is the across-subject mean against a sign-flip null, which is
    the same null shape E192 used, applied to a reference the deposit supplies rather than to a statistic
    I chose.
    """
    ch, re_ = chance_by_subject(), real_by_subject()
    keys = sorted(set(ch) & set(re_))
    d = np.array([re_[k] - ch[k] for k in keys], float)
    if d.size < 10:
        return {"n": int(d.size), "pass": False, "why": "too few subjects with a Chance run"}
    rng = np.random.default_rng(SEED)
    nul = np.array([float((d * np.where(rng.integers(0, 2, d.size) > 0, -1, 1)).mean())
                    for _ in range(REPS)])
    lo = float(np.quantile(nul, 0.05))
    obs = float(d.mean())
    return {"n": int(d.size), "subjects": [k[0] for k in keys],
            "mean_delta": obs, "null_p05": lo,
            "n_better": int((d < 0).sum()),
            "chance_mean": float(np.mean([ch[k] for k in keys])),
            "real_mean": float(np.mean([re_[k] for k in keys])),
            "pass": bool(obs < lo)}


def main() -> int:
    print("E201 — E199's test with the deposit's OWN chance-level runs as the aliveness reference")
    E192.TABLES = [os.path.join(RESULTS, f"cp_last.s{k}.csv") for k in range(4)] + \
                  [os.path.join(RESULTS, "cp_last.csv")]
    OUT = os.path.join(RESULTS, "e201_cp_chance_referenced.json")
    res = {"experiment": "E201", "primary": E192.PRIMARY, "outcome": E192.OUTCOME,
           "e181_mu_mean": E192.E181_MU, "e181_floor": E192.E181_FLOOR}

    a = aliveness()
    res["aliveness_vs_chance"] = a
    print(f"\nG2' ALIVENESS vs the study's own Chance runs — {a['n']} subjects")
    if a["n"] >= 10:
        print(f"   real-run mean distance {a['real_mean']:.4f} vs chance-run {a['chance_mean']:.4f}; "
              f"per-subject delta {a['mean_delta']:+.4f} vs sign-flip 5th pct {a['null_p05']:+.4f}")
        print(f"   {a['n_better']} of {a['n']} subjects track better than their own chance run   "
              f"{'PASS' if a['pass'] else '*** FAIL'}")
    else:
        print(f"   *** {a.get('why')}")

    # The rest is E192's design, reached through E192's own functions so there is ONE implementation of
    # the statistic, the pairing, the floors and the verdict branches. The ONLY substitution is G2' for
    # G2, written out here rather than patched into E192 so the swap is visible in the diff.
    sess, n_rows, _align, spread = E192.build(E192.OUTCOME)
    res["n_trial_rows"], res["n_subjects"] = n_rows, len(sess)
    res["total_pairs"] = int(sum(len(s["pairs"]) for s in sess))
    if not sess:
        res["verdict"], res["why"] = "NOT INTERPRETABLE", "no subject yields enough pairs"
        json.dump(res, open(OUT, "w"), indent=2)
        print(f"VERDICT: {res['verdict']} — {res['why']}")
        return 1
    print(f"   {n_rows} trial rows -> {len(sess)} subjects, {res['total_pairs']} pairs "
          f"(median {np.median([len(s['pairs']) for s in sess]):.0f})")
    g1 = bool(len(sess) >= E192.MIN_SUBJECTS)
    print(f"   G1 {'PASS' if g1 else '*** FAIL'} (floor {E192.MIN_SUBJECTS} subjects)")

    rng = np.random.default_rng(SEED)
    within = np.array([w for w, _ in spread])
    across = np.array([float(np.std(v)) for _, v in spread if v.size > 3])
    ratio = float(np.mean(within / np.maximum(across, 1e-12))) if within.size else float("nan")
    g3 = bool(np.isfinite(ratio) and ratio > 0.30)
    res["G3"] = {"ratio": ratio, "pass": g3}
    print(f"   G3 outcome graded within run: sd_within/sd_subject = {ratio:.3f}   "
          f"{'PASS' if g3 else '*** FAIL'}")

    gaps = np.concatenate([[h - m for (h, m) in s["pairs"]] for s in sess]).astype(float)
    signed = float(gaps.mean())
    gn = np.array([float((gaps * np.where(rng.integers(0, 2, gaps.size) > 0, -1, 1)).mean())
                   for _ in range(REPS)])
    lo, hi = float(np.quantile(gn, 0.025)), float(np.quantile(gn, 0.975))
    idx = {(s["subject"], s["session"]): s["cols"]["_index"] for s in sess}
    io, ip, _, _ = E172.flip_null(sess, E192.PRIMARY, np.random.default_rng(SEED + 2),
                                  reps=1000, override=idx)
    g4 = bool(lo <= signed <= hi and np.isfinite(ip) and ip > E192.ALPHA)
    res["G4"] = {"signed_gap": signed, "null": [lo, hi], "index_p": float(ip), "pass": g4}
    print(f"   G4 pairing balanced: signed gap {signed:+.4f} in [{lo:+.4f}, {hi:+.4f}]; "
          f"trial index {io:.4f}, p = {ip:.4f}   {'PASS' if g4 else '*** FAIL'}")

    if not (a["pass"] and g1 and g3 and g4):
        res["verdict"] = "NOT INTERPRETABLE"
        res["why"] = ("a design gate failed: " + ", ".join(
            n for n, ok in (("G2' aliveness vs the study's own chance runs", a["pass"]),
                            ("G1 subjects", g1), ("G3 graded outcome", g3),
                            ("G4 pairing", g4)) if not ok)
            + ("; subjects do not track better than the study's own chance-level runs, so the deposit "
               "cannot test a graded execution-quality claim at all" if not a["pass"] else ""))
        json.dump(res, open(OUT, "w"), indent=2)
        print("\n" + "=" * 100)
        print(f"VERDICT: {res['verdict']}\n  {res['why']}")
        print("=" * 100)
        return 1

    noise = {(s["subject"], s["session"]): np.random.default_rng(SEED + 7).normal(size=s["n_trials"])
             for s in sess}
    _o, p_noise, _n, _k = E172.flip_null(sess, E192.PRIMARY, np.random.default_rng(SEED + 8),
                                         reps=1000, override=noise)
    print(f"   G5(a) i.i.d. noise p = {p_noise:.4f}   "
          f"{'PASS' if p_noise > E192.ALPHA else '*** FAIL'}")
    floor, ladder = float("nan"), []
    for rho in E192.LADDER:
        inj = {}
        for s in sess:
            g = np.random.default_rng(SEED + 900 + int(rho * 1000))
            v = g.normal(size=s["n_trials"])
            for (h, _m) in s["pairs"]:
                v[h] += rho * 3.0
            inj[(s["subject"], s["session"])] = v
        _o, p, _n, _k = E172.flip_null(sess, E192.PRIMARY, np.random.default_rng(SEED + 13),
                                       reps=1000, override=inj)
        ladder.append({"rho": rho, "p": float(p)})
        print(f"   G5(b) rho = {rho}: p = {p:.4f}")
        if p <= E192.ALPHA and not np.isfinite(floor):
            floor = rho
    res["G5"] = {"noise_p": float(p_noise), "ladder": ladder, "floor": floor,
                 "pass": bool(p_noise > E192.ALPHA and np.isfinite(floor))}
    print(f"   FLOOR: {floor}")

    tab, bh = E192.table_for(sess, E192.OUTCOME)
    res["table"], res["bh"] = tab, bh

    other = {}
    for sc in E192.OTHER_SCORINGS:
        s2, _n2, _a2, _sp2 = E192.build(sc)
        if not s2:
            other[sc] = {"mean": float("nan")}
            continue
        st = E172.frac_stat(s2, E192.PRIMARY)
        lo2, hi2 = E172.cluster_ci(st, np.random.default_rng(SEED + 21))
        other[sc] = {"mean": st["mean"], "ci": [lo2, hi2], "n_sessions": st["n_sessions"]}
        print(f"   [scoring {sc:<14s}] {E192.PRIMARY} = {st['mean']:.4f} [{lo2:.4f}, {hi2:.4f}]")
    res["other_scorings"] = other

    pr = tab[E192.PRIMARY]
    clears = bool(np.isfinite(pr["p"]) and pr["p"] <= E192.ALPHA and res["G5"]["pass"])
    above, below = bool(pr["ci"][0] > 0.5), bool(pr["ci"][1] < 0.5)
    agree = [sc for sc, v in other.items()
             if np.isfinite(v.get("mean", float("nan"))) and v["mean"] < 0.5]
    print("\n" + "=" * 100)
    if clears and above:
        v, why = "REVERSED", (f"{E192.PRIMARY} = {pr['mean']:.4f} with a 95 % interval ENTIRELY ABOVE "
                              f"0.5 ([{pr['ci'][0]:.4f}, {pr['ci'][1]:.4f}]), the OPPOSITE of E181's "
                              f"{E192.E181_MU:.4f}. This REFUTES the direction")
    elif not clears or not below:
        v, why = "ABSENT ABOVE FLOOR", (
            f"{E192.PRIMARY} = {pr['mean']:.4f} [{pr['ci'][0]:.4f}, {pr['ci'][1]:.4f}], "
            f"p = {pr['p']:.4f} against a measured floor of rho = {floor}")
    elif len(agree) <= 1:
        v, why = "FRAGILE", (f"{E192.PRIMARY} = {pr['mean']:.4f} clears on {E192.OUTCOME} but only "
                             f"{len(agree)} of {len(E192.OTHER_SCORINGS)} other scorings agree in sign")
    else:
        v, why = "REPLICATED", (
            f"{E192.PRIMARY} = {pr['mean']:.4f} [{pr['ci'][0]:.4f}, {pr['ci'][1]:.4f}], "
            f"p = {pr['p']:.4f}, in E181's direction ({E192.E181_MU:.4f}), above the measured floor "
            f"rho = {floor}, with {len(agree)} of {len(E192.OTHER_SCORINGS)} scorings agreeing")
    res["verdict"], res["why"] = v, why
    print(f"VERDICT: {v}\n  {why}")
    print("=" * 100)
    print("INDEPENDENCE LIMITATION, unchanged: same laboratory as Stieger, disjoint subjects, different\n"
          "  task -- a subject-and-task replication, not a laboratory-independent one.")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
