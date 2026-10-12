#!/usr/bin/env python3
"""E193 — Challenge A's constructive test, against the null E165 should have used.

REGISTERED BEFORE ANY PERMUTATION DRAW HAS BEEN COMPUTED.

=========================================================================================================
WHAT E165 GOT RIGHT, AND THE ONE THING THAT VOIDED IT
=========================================================================================================
E165 asked Challenge A constructively: is there a LINEAR combination of the spectral family that keeps
behavioural-state discrimination while dropping AGENT discrimination to the floor? Its machinery survived
a rule-40 capability gate that caught a fatal normalisation bug — ranking the conscious and unconscious
blocks separately annihilates the very contrast under test, and the synthetic control returned held-out
state legibility of 0.0056 where jointly ranking gives 0.4323, a factor of 77.

**Its verdict was still not issued, because its success bar was vacuous.** The floor for "agent legibility
dropped to the floor" was the 95th percentile of the statistic over 200 RANDOM WEIGHT VECTORS: **0.4203**.
That is a dispersion, not a null. In a space where some directions genuinely carry the agent label, the
spread across directions is inflated by the very signal under test. The correct reference — a cluster-level
permutation over the case-level arm labels — **had already been measured on this same cohort by E154, at a
95th percentile near 0.19, less than half.** Against a 0.42 bar essentially any projection passes, and the
file duly fired at lambda = 0, with no adversarial term in the objective at all.

**This file changes the NULL and nothing else about the question.** Cohort, features, summarisation,
objective, held-out scheme and the 80 % state-retention tolerance are E165's, unchanged.

=========================================================================================================
THE NULL, COMPUTED THROUGH THE WHOLE PIPELINE
=========================================================================================================
For each lambda, the case-level arm labels are permuted and **the entire leave-one-case-out fit and
evaluation is re-run on the permuted labels**. That matters: the adversarial term uses the arm label, so
permuting only at scoring time would leave the fit informed by the true labels and understate the null.
The floor is that null's 95th percentile, recomputed per lambda because the objective changes with lambda.

The gradient is now ANALYTIC rather than an eleven-point finite difference. For c = corr(Xw, y) on a
centred y, dc/dw = X'(y - c*s)/(n*sd) with s the standardised score — the same objective, computed exactly
and about forty times faster, which is what makes a per-lambda permutation null affordable at all. This
changes no threshold, cohort or estimand.

=========================================================================================================
THE CAPABILITY GATE E165 HAD, AND THE ONE IT DID NOT
=========================================================================================================
G2a  **POSITIVE** (E165's, kept): a synthetic system built from a known state-driving latent must return
     high held-out state legibility. This is what caught the normalisation bug.
G2b  **NEGATIVE (NEW).** A synthetic system in which state and agent are driven by the SAME latent, so
     they are inseparable by construction, must return **NO** lambda that satisfies the success rule. If
     the method "constructs" a separating axis where none can exist, the success rule is unfalsifiable and
     nothing it reports means anything (rule 40). E165 had a control that proved the machinery could
     succeed and none that proved it could fail; that asymmetry is exactly how a vacuous bar survives.

G3   the agent floor is the cluster-level permutation null's 95th percentile, per lambda.
G4   **DURATION MUST NOT BE THE AXIS.** E154 found recording duration identifying the agent at
     |AUC-0.5| = 0.3771 on this very cohort — above every feature but one. Both case summaries are taken
     over a FIXED epoch count so length cannot enter arithmetically; G4 verifies it empirically by
     scoring duration through the same legibility statistic and requiring it to be uncorrelated with the
     learned axis at |rho| < 0.30.

=========================================================================================================
VERDICT — WRONG-DIRECTION CASES FIRST (rule 37)
=========================================================================================================
  (1) NOT INTERPRETABLE   G1 (cohort size), G2a, G2b or G4 fails. Nothing is read.
  (2) VACUOUS             the success rule fires at lambda = 0, i.e. with no adversarial term. That is
                          E165's failure mode and it is enumerated so it cannot be reported as a result.
  (3) NOT CONSTRUCTED     no lambda keeps >= 80 % of the lambda=0 state legibility while putting agent
                          legibility below the cluster-null 95th percentile. **Challenge A is then
                          bounded on this cohort by measurement rather than by assumption.**
  (4) CONSTRUCTED         some lambda > 0 does both.

**REGISTERED PREDICTION: (3) NOT CONSTRUCTED.** E161 found `relative_theta_power` (weighted 0.3263) and
`alpha_peak_hz` (0.2990) each identifying the agent far above a cluster null p95 of ~0.10 on VitalDB, and
E186's own G3 finds the agent legible in every pre-specified subset of the same family. If the agent is
legible in every subset, a linear combination that hides it while keeping depth is unlikely to exist. A
(4) here would be a genuine surprise and would need replication on VitalDB before being believed.

**Why this cohort and not VitalDB:** the state label here is BEHAVIOURAL — the time at which the
probability of response to click and verbal cues fell below 5 % — not a scorer or an index reading the
EEG. Every VitalDB-based Challenge A test in this programme has had to declare that its depth axis is
BIS-derived and therefore partly circular, and E93 measured that axis saturating. This deposit removes
that caveat at the cost of a smaller cohort and spectra-only features.

    python bsde/src/bsde/experiments/e193_adversarial_against_cluster_null.py
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

from bsde.verifier.stats import auc_abs                                        # noqa: E402
from e154_lambda_on_mgh_or import FEATURES, MIN_EPOCHS, TABLE, _f              # noqa: E402
from e155_duration_adjusted_drug_legibility import WINDOW                      # noqa: E402
from e165_adversarial_challenge_a import build, ranks                          # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e193_adversarial_cluster_null.json")
SEED = 20260801

LAMBDAS = (0.0, 0.5, 1.0, 2.0, 4.0, 8.0)
STATE_TOL = 0.80          # E165's, unchanged
PERMS = 200
CORR_MAX = 0.30           # G4: |rho(axis, duration)|
MIN_PER_ARM = 12
ITERS, LR = 400, 0.15


def add_duration(cases):
    """Attach each case's TOTAL epoch count — the variable E154 found identifying the agent at 0.3771.

    E165's `build` does not carry it, so G4 would have scored an all-NaN column and passed by
    construction — a gate that cannot fail (rule 40). It is read here from the same table `build` uses.
    """
    import csv
    from collections import Counter
    n = Counter()
    for r in csv.DictReader(open(TABLE, newline="")):
        if r["cohort"] == "OR":
            n[r["case"]] += 1
    miss = [c for c in cases if c not in n]
    for c in cases:
        cases[c]["n_epochs"] = float(n.get(c, float("nan")))
    return cases, miss


def legibility(score, label):
    m = np.isfinite(score)
    if len(set(label[m].tolist())) < 2 or len(set(score[m].tolist())) < 2:
        return float("nan")
    return auc_abs(list(label[m]), list(score[m])) - 0.5


def _corr_and_grad(X, y, w):
    """corr(Xw, y) for centred y, and its exact gradient in w. See the docstring's derivation."""
    z = X @ w
    m, sd = z.mean(), z.std()
    if sd < 1e-12:
        return 0.0, np.zeros_like(w)
    s = (z - m) / sd
    c = float(np.mean(s * y))
    g = X.T @ (y - c * s) / (len(y) * sd)
    return c, g


def fit_w(Xs, ys, Xa, ya, lam, iters=ITERS, lr=LR, seed=0):
    """Ascent on |corr(w.x, state)| - lam * |corr(w.x, agent)|, on ranks, with w unit-normalised."""
    rng = np.random.default_rng(seed)
    w = rng.standard_normal(Xs.shape[1])
    w /= np.linalg.norm(w) + 1e-12
    for _ in range(iters):
        cs, gs = _corr_and_grad(Xs, ys, w)
        ca, ga = _corr_and_grad(Xa, ya, w)
        g = math.copysign(1.0, cs) * gs - lam * math.copysign(1.0, ca) * ga
        w = w + lr * g
        n = np.linalg.norm(w)
        if n < 1e-12:
            break
        w /= n
    return w


def evaluate(S, U, arm, lam, seed=0):
    """Leave-one-case-out held-out state and agent legibility. S/U are jointly-ranked blocks."""
    n = len(arm)
    Xs = np.vstack([S, U])
    ys = np.concatenate([np.full(n, -1.0), np.full(n, 1.0)])
    ya = (arm - arm.mean()) / (arm.std() + 1e-12)
    st, ag = np.full(2 * n, np.nan), np.full(n, np.nan)
    for i in range(n):
        tr = np.array([j for j in range(n) if j != i])
        trs = np.concatenate([tr, tr + n])
        w = fit_w(Xs[trs], ys[trs], U[tr], ya[tr], lam, seed=seed)
        st[i], st[i + n] = S[i] @ w, U[i] @ w
        ag[i] = U[i] @ w
    state_lab = np.concatenate([np.zeros(n), np.ones(n)])
    return legibility(st, state_lab), legibility(ag, arm), ag


def blocks(cases, ids):
    n = len(ids)
    both = np.column_stack([ranks([cases[c][f"con_{f}"] for c in ids]
                                  + [cases[c][f"unc_{f}"] for c in ids]) for f in FEATURES])
    return both[:n], both[n:]


def synthetic(n, entangled, rng):
    """A system whose answer is known by construction.

    entangled=False: state and agent are driven by INDEPENDENT latents, so a separating axis exists.
    entangled=True:  ONE latent drives both, so no linear combination can keep state and drop agent.
    """
    p = len(FEATURES)
    lat_s = rng.normal(size=n)
    lat_a = lat_s.copy() if entangled else rng.normal(size=n)
    arm = (lat_a > np.median(lat_a)).astype(float)
    ws, wa = rng.normal(size=p), rng.normal(size=p)
    U = 0.9 * np.outer(lat_a, wa) + rng.normal(size=(n, p))
    S = U - 1.2 * np.outer(np.ones(n), ws) - 0.9 * np.outer(lat_s, ws) + rng.normal(size=(n, p)) * 0.3
    st = np.column_stack([ranks(np.concatenate([S[:, j], U[:, j]])) for j in range(p)])
    return st[:n], st[n:], arm


def main() -> int:
    print("E193 — Challenge A constructively, against a CLUSTER-LEVEL PERMUTATION null")
    cases, miss = add_duration(build())
    ids = sorted(cases)
    if miss:
        print(f'   WARNING: {len(miss)} cases have no epoch count')
    arm = np.array([cases[c]["arm"] for c in ids], float)
    n_mix, n_pro = int(arm.sum()), int(len(arm) - arm.sum())
    res = {"experiment": "E193", "n_cases": len(ids), "n_mixed": n_mix, "n_propofol": n_pro,
           "lambdas": list(LAMBDAS), "perms": PERMS, "state_tol": STATE_TOL, "features": FEATURES}
    g1 = bool(min(n_mix, n_pro) >= MIN_PER_ARM)
    print(f"G1 COHORT  {len(ids)} OR cases: {n_pro} propofol alone, {n_mix} mixed   "
          f"{'PASS' if g1 else '*** FAIL'} (floor {MIN_PER_ARM} per arm)")
    res["g1"] = g1

    rng = np.random.default_rng(SEED)
    print("\nG2a POSITIVE capability — independent latents, a separating axis EXISTS by construction")
    Sp, Up, ap = synthetic(len(ids), False, np.random.default_rng(SEED + 1))
    s0p, a0p, _ = evaluate(Sp, Up, ap, 0.0, seed=SEED)
    g2a = bool(np.isfinite(s0p) and s0p > 0.20)
    print(f"    held-out state legibility at lam=0: {s0p:+.4f} (agent {a0p:+.4f})   "
          f"{'PASS' if g2a else '*** FAIL'}")

    print("G2b NEGATIVE capability — ONE latent drives both, so NO axis can separate them")
    Se, Ue, ae = synthetic(len(ids), True, np.random.default_rng(SEED + 2))
    s0e, a0e, _ = evaluate(Se, Ue, ae, 0.0, seed=SEED)
    ent = {}
    for lam in LAMBDAS:
        s, a, _ = evaluate(Se, Ue, ae, lam, seed=SEED)
        nul = []
        for k in range(40):
            pa = np.random.default_rng(SEED + 500 + k).permutation(ae)
            _s2, a2, _ = evaluate(Se, Ue, pa, lam, seed=SEED)
            if np.isfinite(a2):
                nul.append(abs(a2))
        f95 = float(np.quantile(nul, 0.95)) if nul else float("nan")
        ok = bool(np.isfinite(s) and np.isfinite(s0e) and s >= STATE_TOL * abs(s0e)
                  and np.isfinite(a) and abs(a) < f95 and lam > 0)
        ent[str(lam)] = {"state": float(s), "agent": float(a), "floor": f95, "succeeds": ok}
        print(f"    lam {lam:>4.1f}: state {s:+.4f} agent {a:+.4f} floor {f95:+.4f}"
              f"{'   *** SUCCEEDS (should not)' if ok else ''}")
    g2b = not any(v["succeeds"] for v in ent.values())
    print(f"    {'PASS — the success rule can FAIL' if g2b else '*** FAIL — the rule is unfalsifiable'}")
    res["g2a"], res["g2b"], res["entangled_control"] = g2a, g2b, ent

    S, U = blocks(cases, ids)
    dur = np.array([cases[c]["n_epochs"] for c in ids], float)
    print(f"   recording length: {np.nanmin(dur):.0f}-{np.nanmax(dur):.0f} epochs, "
          f"{np.isfinite(dur).sum()} of {len(ids)} cases populated")

    print("\nlambda   state   (>= tol)     agent    cluster-null p95   verdict")
    s0, a0, _ax0 = evaluate(S, U, arm, 0.0, seed=SEED)
    tab = {}
    for lam in LAMBDAS:
        s, a, ax = evaluate(S, U, arm, lam, seed=SEED) if lam else (s0, a0, _ax0)
        nul = []
        for k in range(PERMS):
            pa = np.random.default_rng(SEED + 9000 + k).permutation(arm)
            _s2, a2, _ = evaluate(S, U, pa, lam, seed=SEED)
            if np.isfinite(a2):
                nul.append(abs(a2))
        f95 = float(np.quantile(nul, 0.95)) if nul else float("nan")
        keeps = bool(np.isfinite(s) and np.isfinite(s0) and s >= STATE_TOL * abs(s0))
        hides = bool(np.isfinite(a) and np.isfinite(f95) and abs(a) < f95)
        tab[str(lam)] = {"state": float(s), "agent": float(a), "floor": f95,
                         "keeps_state": keeps, "hides_agent": hides,
                         "succeeds": bool(keeps and hides), "n_null": len(nul)}
        print(f"  {lam:>5.1f}  {s:+.4f}  {'yes' if keeps else ' no'}      {a:+.4f}   "
              f"{f95:+.4f} ({len(nul)})   "
              f"{'SUCCEEDS' if keeps and hides else ('hides' if hides else 'legible')}")
    res["table"], res["state_lam0"] = tab, float(s0)

    ok_lams = [float(k) for k, v in tab.items() if v["succeeds"]]
    pos = [x for x in ok_lams if x > 0]
    _s, _a, ax = evaluate(S, U, arm, pos[0] if pos else 0.0, seed=SEED)
    if np.isfinite(dur).sum() > 10:
        d = dur[np.isfinite(dur) & np.isfinite(ax)]
        v = ax[np.isfinite(dur) & np.isfinite(ax)]
        rho = float(np.corrcoef(np.argsort(np.argsort(d)), np.argsort(np.argsort(v)))[0, 1])
    else:
        rho = float("nan")
    g4 = bool(not np.isfinite(rho) or abs(rho) < CORR_MAX)
    res["g4_axis_vs_duration_rho"], res["g4"] = rho, g4
    print(f"\nG4 axis vs recording length: rho = {rho:+.4f}   {'PASS' if g4 else '*** FAIL'} "
          "(both summaries use a fixed epoch count, so this is a check rather than a correction)")

    print("\n" + "=" * 100)
    if not (g1 and g2a and g2b and g4):
        v, why = "NOT INTERPRETABLE", (
            "a gate failed: " + ", ".join(n for n, ok in (("G1 cohort", g1),
                                                          ("G2a positive capability", g2a),
                                                          ("G2b negative capability", g2b),
                                                          ("G4 duration", g4)) if not ok))
    elif ok_lams and not pos:
        v, why = "VACUOUS", (
            "the success rule fires only at lambda = 0, i.e. with NO adversarial term in the objective. "
            "That is E165's failure mode and it is not a result")
    elif pos:
        v, why = "CONSTRUCTED", (
            f"lambda {pos} keeps >= {STATE_TOL:.0%} of the lambda=0 state legibility "
            f"({s0:+.4f}) while putting agent legibility below the cluster-permutation 95th percentile")
    else:
        v, why = "NOT CONSTRUCTED", (
            f"no lambda keeps >= {STATE_TOL:.0%} of the lambda=0 state legibility ({s0:+.4f}) while "
            "dropping agent legibility below the cluster-permutation floor; on this cohort, with a "
            "BEHAVIOURAL state label, depth and agent identity are not linearly separable in the "
            "spectral family")
    res["verdict"], res["why"] = v, why
    print(f"VERDICT: {v}\n  {why}")
    print("=" * 100)

    os.makedirs(RESULTS, exist_ok=True)
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
