#!/usr/bin/env python3
"""E192 — external replication of E181's GRADED execution-quality finding, on continuous pursuit.

REGISTERED BEFORE THE CONTINUOUS-PURSUIT TABLE EXISTS. The extractor was running when this was written and
no feature or outcome value from it has been inspected.

=========================================================================================================
THE ONE CHALLENGE B RESULT STILL STANDING, AND THE TEST IT HAS NEVER HAD
=========================================================================================================
E172 found a pre-cue alpha effect on Stieger's BINARY hit/miss construct. **E174 did not replicate it on
held-out sessions and E188 did not replicate it on Dreyer 2023** — the latter with 72 subjects, 3,544
matched pairs, a live decoder (out-of-fold AUC 0.6387 against a permuted p95 of 0.5067) and, for the first
time in this project, REAL EMG channels, which were themselves null (0.4994, p = 0.9720). That construct
is finished.

**E181 is what survived**, and it is a different claim: on a GRADED outcome — how quickly a correctly
followed command is executed — pre-cue alpha predicts execution, discovered on 118 Stieger sessions
(`mu_mean` 0.4803 [0.4681, 0.4925], p = 0.0000, measured floor rho = 0.02) and confirmed on the untouched
session 1 (0.4799, one-sided p = 0.0255). **E188 could not test it at all**: the Graz paradigm gives a
fixed feedback period, so there is no graded execution quality to score, and its arm B substituted a
confidence proxy that was declared as the weaker analogue before that run.

Forenzo & He's continuous-pursuit deposit supplies exactly the missing outcome. A cursor driven by motor
imagery follows a randomly drifting target for 60 s while cursor and target positions are logged at 25 Hz,
so **every trial carries a continuous execution-quality score** rather than a hit or a miss.

=========================================================================================================
DIRECTION IS FIXED BEFORE THE RUN, AND IT IS THE UNCOMFORTABLE ONE
=========================================================================================================
`frac_stat` is the fraction of matched pairs in which the candidate is LARGER on the BETTER trial. E181's
`mu_mean` came in at **0.4803, below 0.5** — so on Stieger, **higher pre-cue alpha goes with the WORSE
(slower) trial**. That is the direction this file predicts, stated now so it cannot be re-read afterwards:
**`mu_mean` < 0.5, meaning pre-trial alpha is LOWER on the better-tracked trial.** A result above 0.5 with
an interval excluding it is a REVERSAL, not a replication, and is enumerated as its own verdict (rule 37,
whose fourth occurrence was exactly a refutation printed as a confirmation).

=========================================================================================================
PRIMARY, AND THE FOUR SCORINGS
=========================================================================================================
The extractor stores four scorings of the same 60 s execution — `mean_dist`, `median_dist`, `frac_within`
and `vel_alignment` — deliberately, so that picking one afterwards would be visible. **The primary is
`mean_dist`** (lower = better tracking), declared here. The other three are reported beside it as a
consistency check and carry no verdict; a primary that fires while all three disagree is reported as
FRAGILE rather than as a replication.

**The primary candidate is `mu_mean`**, E172/E181's own measure. Every other candidate is secondary and
BH-corrected.

=========================================================================================================
GATES
=========================================================================================================
G1  >= 20 subjects with >= 25 matched adjacent-trial pairs each. The floor is lower than E188's 50 because
    this deposit has 28 subjects in total; it is set from the deposit's size, not from what passes.
G2  **THE BCI MUST BE ALIVE.** Pooled `vel_alignment` — the cosine between cursor velocity and the
    direction to the target — must exceed its own within-subject sign-flip null. If the cursor is not
    actually being driven toward the target, "execution quality" is not measuring execution and nothing
    downstream means anything (rule 53: check the phenomenon exists in this cohort before asking who has
    more of it).
G3  **THE OUTCOME MUST BE GRADED WITHIN A RUN.** The within-run spread of `mean_dist` must exceed a
    permutation reference that shuffles trials across runs within a subject. A pairing design needs
    within-run contrast; if tracking quality is a subject-level constant, there is nothing to pair on.
G4  (a) the pairing is directionally balanced against its own flip null, using E174's balancer;
    (b) the trial index within the run must NOT itself predict the outcome ordering — trials 0-4 of a run
    could carry fatigue or warm-up, and that would masquerade as a feature effect.
G5  (a) an i.i.d. noise column is NOT detected; (b) a rho ladder gives the measured detection floor, and
    no candidate below that floor may be called present.

=========================================================================================================
VERDICT — WRONG-DIRECTION CASES FIRST (rule 37)
=========================================================================================================
  (1) NOT INTERPRETABLE   G1, G2, G3 or G4 fails. Nothing is read.
  (2) REVERSED            `mu_mean` clears its floor with an interval ABOVE 0.5. This REFUTES E181's
                          direction and must never be written as support.
  (3) ABSENT ABOVE FLOOR  `mu_mean` does not clear the measured floor. E181 is then non-replicated on the
                          graded outcome as well, and Challenge B has no surviving external result.
  (4) FRAGILE             `mu_mean` clears in E181's direction on the primary scoring but at least two of
                          the three other scorings sit on the other side of 0.5.
  (5) REPLICATED          `mu_mean` clears in E181's direction, and the other scorings agree in sign.

**REGISTERED PREDICTION: (3) ABSENT ABOVE FLOOR.** Two of the three prior external or held-out tests of a
pre-cue alpha effect in this project have returned absent, and the one that survived did so on the deposit
it was discovered in. Predicting (5) here would be predicting against this project's own base rate. This
file exists because the prediction may be wrong and because E181 has never had the test — not because a
positive is expected.

**Independence limitation, declared now:** this deposit and Stieger's come from the same laboratory
(He, CMU) with overlapping apparatus and protocol lineage. The subjects are disjoint and the task is
different, so this is a subject-and-task replication, **not** a laboratory-independent one. Dreyer 2023
supplied that independence and could not supply the graded outcome; no single available deposit supplies
both, and saying so is more honest than picking one and calling it external.

    python bsde/src/bsde/experiments/e192_continuous_pursuit_graded_replication.py
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
sys.path.insert(0, HERE)

import e172_matched_pair_trial_responsiveness as E172                            # noqa: E402
from e174_trial_replication_heldout_sessions import _balanced_pairs              # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
TABLES = [os.path.join(RESULTS, f"cp_trials.s{k}.csv") for k in range(4)] + \
         [os.path.join(RESULTS, "cp_trials.csv")]
OUT = os.path.join(RESULTS, "e192_continuous_pursuit_graded.json")
E181_JSON = os.path.join(RESULTS, "e181_trial_length_graded_outcome.json")
SEED = 20260801

PRIMARY = "mu_mean"
OUTCOME = "mean_dist"                     # lower is better tracking
OTHER_SCORINGS = ["median_dist", "frac_within", "vel_alignment"]
BETTER_IS_LOWER = {"mean_dist": True, "median_dist": True,
                   "frac_within": False, "vel_alignment": False}
CANDIDATES = ["mu_mean", "mu_c3", "mu_c4", "mu_lateralisation",
              "relative_alpha_power", "relative_delta_power", "exponent_low", "exponent_high",
              "whole_head_exponent", "spectral_edge_95", "spectral_entropy", "lempel_ziv",
              "emg_index"]
MIN_PAIRS = 25
MIN_SUBJECTS = 20
REPS = 2000
ALPHA = 0.05
LADDER = (0.02, 0.05, 0.10, 0.20)

try:
    _e181 = json.load(open(E181_JSON))
    E181_MU = float(_e181["discovery"]["table"][PRIMARY]["mean"])
    E181_FLOOR = float(_e181["discovery"]["floor"])
except Exception:                                                              # noqa: BLE001
    E181_MU, E181_FLOOR = float("nan"), float("nan")


def _f(v):
    try:
        x = float(v)
        return x if np.isfinite(x) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def load():
    by, n = defaultdict(list), 0
    seen = set()
    for p in TABLES:
        if not os.path.exists(p):
            continue
        with open(p, newline="") as fh:
            for r in csv.DictReader(fh):
                key = (r["subject"], r["session"], r["run"], r["decoder"], r["trial"])
                if key in seen:                       # rule 56: de-duplicate on the key when loading
                    continue
                seen.add(key)
                by[r["subject"]].append(r)
                n += 1
    for s in by:
        by[s].sort(key=lambda r: (r["session"], r["decoder"], r["run"], int(r["trial"])))
    return by, n


def build(scoring):
    """Matched ADJACENT-trial pairs within a run, ordered (better, worse) for `scoring`."""
    by, n_rows = load()
    sess, align, spread = [], [], []
    for sub, rr in sorted(by.items()):
        y = np.array([_f(r[scoring]) for r in rr])
        runkey = [(r["session"], r["decoder"], r["run"]) for r in rr]
        tidx = np.array([_f(r["trial"]) for r in rr])
        pairs = []
        for i in range(len(rr) - 1):
            if runkey[i] != runkey[i + 1]:
                continue
            if tidx[i + 1] != tidx[i] + 1:
                continue
            a, b = y[i], y[i + 1]
            if not (np.isfinite(a) and np.isfinite(b)) or a == b:
                continue
            better_first = (a < b) if BETTER_IS_LOWER[scoring] else (a > b)
            pairs.append((i, i + 1) if better_first else (i + 1, i))
        pairs = _balanced_pairs(pairs, sub, scoring)
        if len(pairs) < MIN_PAIRS:
            continue
        cols = {c: np.array([_f(r.get(c, "")) for r in rr]) for c in CANDIDATES}
        cols["_index"] = tidx.astype(float)
        sess.append({"subject": sub, "session": scoring, "pairs": pairs, "cols": cols,
                     "n_trials": len(rr)})
        va = np.array([_f(r["vel_alignment"]) for r in rr])
        align.append(va[np.isfinite(va)])
        # within-run spread of the outcome, against a subject-level shuffle across runs
        g = defaultdict(list)
        for k, rk in enumerate(runkey):
            if np.isfinite(y[k]):
                g[rk].append(y[k])
        w = [float(np.std(v)) for v in g.values() if len(v) >= 3]
        if w:
            spread.append((float(np.mean(w)), y[np.isfinite(y)]))
    return sess, n_rows, align, spread


def table_for(sess, tag, one_sided=None):
    out, ps = {}, []
    print(f"\n   [{tag}] {'candidate':<24s} {'frac better>worse':>18s} {'[95% CI]':>20s} "
          f"{'same side':>10s} {'p':>8s}")
    names = [c for c in CANDIDATES if c in sess[0]["cols"]]
    for c in names:
        st = E172.frac_stat(sess, c)
        _obs, p, _nm, _k = E172.flip_null(sess, c, np.random.default_rng(SEED + 11), reps=REPS)
        if one_sided is not None and np.isfinite(p):
            p = p / 2.0 if (np.sign(st["mean"] - 0.5) == one_sided) else 1.0 - p / 2.0
        lo, hi = E172.cluster_ci(st, np.random.default_rng(SEED + 12))
        out[c] = {"mean": st["mean"], "ci": [lo, hi], "frac_same_side": st["frac_same_side"],
                  "p": float(p), "n_sessions": st["n_sessions"]}
        ps.append(p)
        print(f"   [{tag}] {c:<24s} {st['mean']:>18.4f} [{lo:>8.4f},{hi:>8.4f}] "
              f"{st['frac_same_side']:>10.2f} {p:>8.4f}"
              + ("   <- PRIMARY" if c == PRIMARY else ""))
    order = np.argsort(ps)
    m = len(ps)
    bh = set()
    for rank, i in enumerate(order, 1):
        if ps[i] <= ALPHA * rank / m:
            bh = set(np.asarray(names)[order[:rank]].tolist())
    print(f"   [{tag}] BH q={ALPHA}: {sorted(bh) or 'none'}")
    return out, sorted(bh)


def main() -> int:
    print("E192 — E181's graded execution-quality finding, tested on continuous pursuit")
    print(f"   E181's discovery bar: {PRIMARY} = {E181_MU:.4f} (floor rho = {E181_FLOOR}); "
          f"direction predicted here: BELOW 0.5")
    res = {"experiment": "E192", "primary": PRIMARY, "outcome": OUTCOME,
           "e181_mu_mean": E181_MU, "e181_floor": E181_FLOOR}

    sess, n_rows, align, spread = build(OUTCOME)
    res["n_trial_rows"], res["n_subjects"] = n_rows, len(sess)
    res["total_pairs"] = int(sum(len(s["pairs"]) for s in sess))
    if not sess:
        res["verdict"], res["why"] = "NOT INTERPRETABLE", "no subject yields enough pairs"
        json.dump(res, open(OUT, "w"), indent=2)
        print(f"VERDICT: {res['verdict']} — {res['why']}")
        return 1
    print(f"   {n_rows} trial rows -> {len(sess)} subjects, {res['total_pairs']} pairs "
          f"(median {np.median([len(s['pairs']) for s in sess]):.0f})")

    g1 = bool(len(sess) >= MIN_SUBJECTS)
    print(f"   G1 {'PASS' if g1 else '*** FAIL'} (floor {MIN_SUBJECTS} subjects, {MIN_PAIRS} pairs)")

    rng = np.random.default_rng(SEED)
    per_sub = np.array([float(np.mean(a)) for a in align if a.size])
    obs = float(per_sub.mean()) if per_sub.size else float("nan")
    nul = np.array([float((per_sub * np.where(rng.integers(0, 2, per_sub.size) > 0, -1, 1)).mean())
                    for _ in range(REPS)]) if per_sub.size else np.array([])
    g2 = bool(nul.size and obs > float(np.quantile(nul, 0.95)))
    res["G2"] = {"vel_alignment": obs,
                 "null_p95": float(np.quantile(nul, 0.95)) if nul.size else float("nan"),
                 "pass": g2}
    print(f"   G2 BCI alive: pooled cursor-to-target velocity alignment {obs:+.4f} vs sign-flip p95 "
          f"{res['G2']['null_p95']:+.4f}   {'PASS' if g2 else '*** FAIL'}")

    within = np.array([w for w, _ in spread])
    across = np.array([float(np.std(v)) for _, v in spread if v.size > 3])
    ratio = float(np.mean(within / np.maximum(across, 1e-12))) if within.size else float("nan")
    g3 = bool(np.isfinite(ratio) and ratio > 0.30)
    res["G3"] = {"within_run_sd": float(np.mean(within)) if within.size else float("nan"),
                 "subject_sd": float(np.mean(across)) if across.size else float("nan"),
                 "ratio": ratio, "pass": g3}
    print(f"   G3 outcome graded within run: sd_within/sd_subject = {ratio:.3f}   "
          f"{'PASS' if g3 else '*** FAIL'}")

    gaps = np.concatenate([[h - m for (h, m) in s["pairs"]] for s in sess]).astype(float)
    signed = float(gaps.mean())
    gn = np.array([float((gaps * np.where(rng.integers(0, 2, gaps.size) > 0, -1, 1)).mean())
                   for _ in range(REPS)])
    lo, hi = float(np.quantile(gn, 0.025)), float(np.quantile(gn, 0.975))
    idx = {(s["subject"], s["session"]): s["cols"]["_index"] for s in sess}
    io, ip, _, _ = E172.flip_null(sess, PRIMARY, np.random.default_rng(SEED + 2), reps=1000,
                                  override=idx)
    g4 = bool(lo <= signed <= hi and np.isfinite(ip) and ip > ALPHA)
    res["G4"] = {"signed_gap": signed, "null": [lo, hi], "index_mean": float(io),
                 "index_p": float(ip), "pass": g4}
    print(f"   G4 pairing balanced: signed gap {signed:+.4f} in [{lo:+.4f}, {hi:+.4f}]; "
          f"trial index {io:.4f}, p = {ip:.4f}   {'PASS' if g4 else '*** FAIL'}")

    if not (g1 and g2 and g3 and g4):
        res["verdict"] = "NOT INTERPRETABLE"
        res["why"] = ("a design gate failed: "
                      + ", ".join(n for n, ok in (("G1 subjects", g1), ("G2 BCI alive", g2),
                                                  ("G3 graded outcome", g3),
                                                  ("G4 pairing", g4)) if not ok))
        json.dump(res, open(OUT, "w"), indent=2)
        print(f"\nVERDICT: {res['verdict']} — {res['why']}")
        return 1

    # G5 -- the measured detection floor, on this cohort with this pairing
    noise = {(s["subject"], s["session"]): np.random.default_rng(SEED + 7).normal(size=s["n_trials"])
             for s in sess}
    _o, p_noise, _n, _k = E172.flip_null(sess, PRIMARY, np.random.default_rng(SEED + 8),
                                         reps=1000, override=noise)
    print(f"   G5(a) i.i.d. noise p = {p_noise:.4f}   "
          f"{'PASS' if p_noise > ALPHA else '*** FAIL'}")
    floor, ladder = float("nan"), []
    for rho in LADDER:
        inj = {}
        for s in sess:
            g = np.random.default_rng(SEED + 900 + int(rho * 1000))
            yv = np.array([1.0 if (h < m) else -1.0 for (h, m) in s["pairs"]])
            v = g.normal(size=s["n_trials"])
            for pi, (h, m) in enumerate(s["pairs"]):
                v[h] += rho * 3.0 * (1.0 if yv[pi] > 0 else 1.0)
            inj[(s["subject"], s["session"])] = v
        _o, p, _n, _k = E172.flip_null(sess, PRIMARY, np.random.default_rng(SEED + 13),
                                       reps=1000, override=inj)
        ladder.append({"rho": rho, "p": float(p)})
        print(f"   G5(b) rho = {rho}: p = {p:.4f}")
        if p <= ALPHA and not np.isfinite(floor):
            floor = rho
    res["G5"] = {"noise_p": float(p_noise), "ladder": ladder, "floor": floor,
                 "pass": bool(p_noise > ALPHA and np.isfinite(floor))}
    print(f"   FLOOR: {floor}")

    tab, bh = table_for(sess, OUTCOME, one_sided=None)
    res["table"], res["bh"] = tab, bh

    other = {}
    for sc in OTHER_SCORINGS:
        s2, _n2, _a2, _sp2 = build(sc)
        if not s2:
            other[sc] = {"mean": float("nan")}
            continue
        st = E172.frac_stat(s2, PRIMARY)
        lo2, hi2 = E172.cluster_ci(st, np.random.default_rng(SEED + 21))
        other[sc] = {"mean": st["mean"], "ci": [lo2, hi2], "n_sessions": st["n_sessions"]}
        print(f"   [scoring {sc:<14s}] {PRIMARY} = {st['mean']:.4f} [{lo2:.4f}, {hi2:.4f}]")
    res["other_scorings"] = other

    # ---- verdict, wrong-direction case enumerated FIRST (rule 37) ---------------------------------
    pr = tab[PRIMARY]
    clears = bool(np.isfinite(pr["p"]) and pr["p"] <= ALPHA and res["G5"]["pass"])
    above = bool(pr["ci"][0] > 0.5)
    below = bool(pr["ci"][1] < 0.5)
    agree = [sc for sc, v in other.items()
             if np.isfinite(v.get("mean", np.nan)) and (v["mean"] < 0.5)]
    print("\n" + "=" * 100)
    if clears and above:
        v, why = "REVERSED", (
            f"{PRIMARY} = {pr['mean']:.4f} with a 95 % interval ENTIRELY ABOVE 0.5 "
            f"([{pr['ci'][0]:.4f}, {pr['ci'][1]:.4f}]), the OPPOSITE of E181's {E181_MU:.4f}. This "
            "REFUTES the direction and must not be reported as a replication")
    elif not clears or not below:
        v, why = "ABSENT ABOVE FLOOR", (
            f"{PRIMARY} = {pr['mean']:.4f} [{pr['ci'][0]:.4f}, {pr['ci'][1]:.4f}], p = {pr['p']:.4f} "
            f"against a measured floor of rho = {floor}; E181's graded finding does not replicate on "
            "the continuous-pursuit outcome")
    elif len(agree) <= 1:
        v, why = "FRAGILE", (
            f"{PRIMARY} = {pr['mean']:.4f} clears in E181's direction on {OUTCOME}, but only "
            f"{len(agree)} of {len(OTHER_SCORINGS)} other scorings of the same execution agree in sign "
            f"({agree}); one scoring is not a replication")
    else:
        v, why = "REPLICATED", (
            f"{PRIMARY} = {pr['mean']:.4f} [{pr['ci'][0]:.4f}, {pr['ci'][1]:.4f}], p = {pr['p']:.4f}, "
            f"in E181's direction ({E181_MU:.4f}) and above the measured floor rho = {floor}; "
            f"{len(agree)} of {len(OTHER_SCORINGS)} other scorings agree in sign")
    res["verdict"], res["why"] = v, why
    print(f"VERDICT: {v}\n  {why}")
    print("=" * 100)
    print("INDEPENDENCE LIMITATION, declared at registration: this deposit and Stieger's come from the\n"
          "  same laboratory. Subjects are disjoint and the task differs, so this is a subject-and-task\n"
          "  replication, NOT a laboratory-independent one. Dreyer 2023 supplied that independence and\n"
          "  could not supply the graded outcome.")

    os.makedirs(RESULTS, exist_ok=True)
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
