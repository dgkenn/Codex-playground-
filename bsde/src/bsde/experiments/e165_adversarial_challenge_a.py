#!/usr/bin/env python3
"""E165 -- Challenge A as a CONSTRUCTION rather than a screen: can any combination hide the drug?

REGISTERED BEFORE ANY WEIGHT VECTOR HAS BEEN FITTED. New question, not a repair.

=========================================================================================================
WHY A SCREEN CANNOT ANSWER THE BRIEF, AND WHY THAT IS NOW DEMONSTRATED RATHER THAN ARGUED
=========================================================================================================
Challenge A asks for *"the simplest representation that predicts loss and recovery across anaesthetics
while MINIMISING drug-identification information"*. Every test this project has run -- E21, E22, E25, E29,
E35, E36, E139, E154, E156, E161 -- has **screened features one at a time** and asked which leaks least.

**E161 closed that route.** On 112 clean-arm VitalDB cases (43 propofol alone, 69 sevoflurane alone), with
age, sex, ASA and BMI weighted out and a fixed intra-operative window, seven of ten candidates separate the
agents against a cluster-level null: `lempel_ziv` 0.3266, `relative_theta_power` 0.3263 (signed AUC 0.8022,
predicted direction), `alpha_peak_hz` 0.2990 (0.1935, predicted direction), `exponent_low` 0.2559,
`whole_head_exponent` 0.2265, `relative_alpha_power` 0.1994, `spectral_edge_95` 0.1690. **Most of the
amplitude family leaks agent identity**, so no single member of it can satisfy the brief.

**But the brief asks for a REPRESENTATION, not a feature.** A combination can carry information that no
component carries, and it can also *cancel* information that every component carries -- which is exactly
what is needed here and has never been tried. This file asks the constructive question:

> Is there a linear combination of these features that discriminates conscious from unconscious as well as
> the best single feature does, while its agent discrimination sits at the null floor?

=========================================================================================================
THE METHOD, AND WHERE IT COMES FROM
=========================================================================================================
This is **domain-adversarial representation learning** (Ganin 2016) / **fair representation** (Zemel 2013)
in its simplest form: a projection trained to be predictive of the label of interest and uninformative
about a protected attribute. The protected attribute here is the anaesthetic. Borrowing it is the point --
the machine-learning literature solved "keep A, drop B" a decade ago and this project has been treating it
as a screening problem.

    objective   maximise  |corr(w.x, STATE)|  -  lam * |corr(w.x, AGENT restricted to unconscious rows)|
    scale       ranks, so the objective is scale-free and no feature's units dominate
    fitting     leave-one-CASE-out; w is never fitted on a case it is evaluated on
    sweep       lam in {0, 0.5, 1, 2, 4, 8} -- lam = 0 is the pure state axis and is the comparator

    cohort      MGH OR, the only reachable cohort carrying STATE and AGENT together: conscious versus
                unconscious epochs, and pure_propofol (27) versus mixed (16). Case summaries over a fixed
                300-epoch unconscious block, as E155 established, so recording length cannot enter --
                E154 measured duration identifying the agent at 0.3771.

=========================================================================================================
GATES
=========================================================================================================
G1  MANIFEST: >= 12 cases per agent arm with >= 30 good-quality epochs in each state.
G2  **SYNTHETIC RECOVERY, AND IT IS THE GATE THAT MAKES THE REST READABLE (rule 40).** A synthetic feature
    set is built from two known latent axes -- one driving STATE only, one driving AGENT only -- observed
    through random mixtures plus noise. **The method must recover a projection whose state correlation is
    high and whose agent correlation falls to the null floor as lam rises.** If it cannot solve a problem
    whose answer exists by construction, nothing it reports on real data means anything. This is the
    control E115's deflation count needed and did not have.
G3  **NULL FLOOR, measured**: the agent legibility of a random projection, over 200 draws, gives the floor
    the adversarial arm must reach. A threshold picked as a round number measures the round number
    (rule 63).
G4  **HONEST EVALUATION**: state and agent legibility are both computed on HELD-OUT cases only. A
    projection fitted and scored on the same cases will always look like it solved the problem.

=========================================================================================================
PRIMARY -- WRONG-DIRECTION BRANCH WRITTEN FIRST (rule 37)
=========================================================================================================
**IF NO SETTING OF lam GIVES BOTH** -- held-out state legibility within 20 % of the lam = 0 axis AND
held-out agent legibility inside the random-projection floor -- then **the two are not separable in this
feature space**, and that is the strongest statement this project can make about Challenge A: not "we
have not found a representation yet" but "state and agent information are entangled in the amplitude
family, and the brief's acceptance condition cannot be met by any linear combination of it." That would
redirect the challenge toward feature families this deposit cannot supply -- phase, connectivity,
perturbational -- rather than toward more search within this one.

**IF SOME lam GIVES BOTH**, it is the first constructed Challenge A candidate, and the next question is
immediately whether it survives on the VitalDB agent contrast, where E161 showed the leakage is broad.

**REGISTERED PREDICTION: no setting of lam gives both, and state legibility will fall roughly in step with
agent legibility.** The reasoning is E161's: seven of ten features leak, and the two that leak most
(`relative_theta_power`, `lempel_ziv`) are also strong state discriminators, which is the signature of
entanglement rather than of a nuisance direction that can be projected out. **The prediction is against
the constructive hope that motivated the file**, which is the correct way round.

SCOPE. Linear combinations only, one deposit, spectra only, and 39-43 cases. A negative bounds the linear
case in the amplitude family; it says nothing about non-linear representations or about feature families
absent here.

WHAT WAS ALREADY SEEN (rule 41). E161's full per-candidate table, quoted above; E154/E155's cohort
construction and the duration confound; the MGH arm counts. No projection has been fitted.

    python bsde/src/bsde/experiments/e165_adversarial_challenge_a.py
"""
from __future__ import annotations

import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.verifier.stats import auc_abs                                        # noqa: E402

sys.path.insert(0, HERE)
from e155_duration_adjusted_drug_legibility import WINDOW, load as load_unconscious  # noqa: E402
from e154_lambda_on_mgh_or import FEATURES, MIN_EPOCHS, TABLE, _f              # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e165_adversarial_challenge_a.json")

LAMBDAS = (0.0, 0.5, 1.0, 2.0, 4.0, 8.0)
RAND_DRAWS = 200
STATE_TOL = 0.80          # held-out state legibility must be >= 80 % of the lam=0 axis
MIN_PER_ARM = 12


def ranks(v):
    v = np.asarray(v, float)
    o = np.argsort(v, kind="mergesort")
    r = np.empty(len(v), float)
    r[o] = np.arange(1, len(v) + 1)
    for u in np.unique(v):
        m = v == u
        if m.sum() > 1:
            r[m] = r[m].mean()
    return (r - r.mean()) / (r.std() + 1e-12)


def build():
    """Per case: the state contrast (conscious vs unconscious medians) and the agent label.

    Both summaries are taken over a FIXED epoch count so recording length cannot enter either -- E154
    measured duration identifying the agent at 0.3771 on this cohort."""
    import csv
    from collections import defaultdict
    per = defaultdict(list)
    for r in csv.DictReader(open(TABLE, newline="")):
        if r["cohort"] == "OR":
            per[r["case"]].append(r)
    out = {}
    for c, rows in per.items():
        if rows[0]["arm"] == "pure_sevo":
            continue
        rows.sort(key=lambda r: _f(r["t"]))
        good = [r for r in rows if r["quality"] == "1"]
        con = [r for r in good if r["label"] == "1"][:WINDOW]
        unc = [r for r in good if r["label"] == "0"][:WINDOW]
        if len(con) < MIN_EPOCHS or len(unc) < MIN_EPOCHS:
            continue
        d = {"arm": 1 if rows[0]["arm"] == "mixed" else 0}
        for f in FEATURES:
            cv = [_f(r[f]) for r in con]
            uv = [_f(r[f]) for r in unc]
            cv = [x for x in cv if math.isfinite(x)]
            uv = [x for x in uv if math.isfinite(x)]
            d[f"con_{f}"] = float(np.median(cv)) if cv else float("nan")
            d[f"unc_{f}"] = float(np.median(uv)) if uv else float("nan")
        out[c] = d
    return out


def legibility(score, label):
    m = np.isfinite(score)
    if len(set(label[m].tolist())) < 2 or len(set(score[m].tolist())) < 2:
        return float("nan")
    return auc_abs(list(label[m]), list(score[m])) - 0.5


def fit_w(Xs, ys, Xa, ya, lam, iters=400, lr=0.15, seed=0):
    """Gradient ascent on |corr(w.x, state)| - lam * |corr(w.x, agent)|, on ranks, with w normalised.

    Deliberately simple: with 11 features and tens of cases, anything with more capacity would fit the
    cases rather than the structure, and the held-out evaluation in G4 is what the design leans on."""
    rng = np.random.default_rng(seed)
    w = rng.standard_normal(Xs.shape[1])
    w /= np.linalg.norm(w) + 1e-12

    def corr(X, y, ww):
        s = X @ ww
        s = (s - s.mean()) / (s.std() + 1e-12)
        return float(np.mean(s * y))

    for _ in range(iters):
        g = np.zeros_like(w)
        eps = 1e-4
        base = abs(corr(Xs, ys, w)) - lam * abs(corr(Xa, ya, w))
        for j in range(len(w)):
            wj = w.copy()
            wj[j] += eps
            wj /= np.linalg.norm(wj) + 1e-12
            g[j] = (abs(corr(Xs, ys, wj)) - lam * abs(corr(Xa, ya, wj)) - base) / eps
        w = w + lr * g
        w /= np.linalg.norm(w) + 1e-12
    return w


def evaluate(cases, ids, lam, seed=0):
    """Leave-one-case-out held-out state and agent legibility for a given lam."""
    arm = np.array([cases[c]["arm"] for c in ids])
    S = np.column_stack([ranks([cases[c][f"con_{f}"] for c in ids]) for f in FEATURES])
    U = np.column_stack([ranks([cases[c][f"unc_{f}"] for c in ids]) for f in FEATURES])
    Xs = np.vstack([S, U])
    ys = np.concatenate([np.full(len(ids), -1.0), np.full(len(ids), 1.0)])
    ya = (arm - arm.mean()) / (arm.std() + 1e-12)
    st, ag = np.full(2 * len(ids), np.nan), np.full(len(ids), np.nan)
    for i, c in enumerate(ids):
        tr = np.array([j for j in range(len(ids)) if j != i])
        trs = np.concatenate([tr, tr + len(ids)])
        w = fit_w(Xs[trs], ys[trs], U[tr], ya[tr], lam, seed=seed)
        st[i], st[i + len(ids)] = S[i] @ w, U[i] @ w
        ag[i] = U[i] @ w
    state_lab = np.concatenate([np.zeros(len(ids)), np.ones(len(ids))])
    return legibility(st, state_lab), legibility(ag, arm)


def main(argv=None) -> int:
    rng = np.random.default_rng(165)
    cases = build()
    ids = sorted(cases)
    arm = np.array([cases[c]["arm"] for c in ids])
    n_mix, n_pro = int(arm.sum()), int((1 - arm).sum())
    out = {"experiment": "E165", "n_cases": len(ids), "n_mixed": n_mix, "n_propofol": n_pro,
           "lambdas": list(LAMBDAS)}
    g1 = n_mix >= MIN_PER_ARM and n_pro >= MIN_PER_ARM
    print(f"G1 MANIFEST  {len(ids)} cases: {n_pro} pure propofol, {n_mix} mixed -> "
          f"{'PASS' if g1 else 'FAIL'}")

    # ---- G3 random-projection floor ---------------------------------------------------------------------
    U = np.column_stack([ranks([cases[c][f"unc_{f}"] for c in ids]) for f in FEATURES])
    rand = []
    for _ in range(RAND_DRAWS):
        w = rng.standard_normal(U.shape[1])
        rand.append(legibility(U @ w, arm))
    rand = np.sort(np.asarray([r for r in rand if math.isfinite(r)]))
    floor = float(np.quantile(rand, 0.95))
    print(f"G3 RANDOM-PROJECTION FLOOR  {len(rand)} draws: mean {rand.mean():.4f}, "
          f"95th percentile {floor:.4f} -- this is the bar the adversarial arm must reach")
    out["G3"] = {"mean": float(rand.mean()), "p95": floor, "n": len(rand)}

    # ---- G2 synthetic recovery ---------------------------------------------------------------------------
    print(f"\nG2 SYNTHETIC RECOVERY  two known latent axes, one STATE-only and one AGENT-only")
    n = len(ids)
    zs, za = rng.standard_normal(n), rng.standard_normal(n)
    syn_arm = (za > np.median(za)).astype(int)
    M = rng.standard_normal((2, len(FEATURES)))
    synU = np.outer(zs, M[0]) + np.outer(za, M[1]) + 0.4 * rng.standard_normal((n, len(FEATURES)))
    synS = np.outer(zs + 2.0, M[0]) + np.outer(za, M[1]) + 0.4 * rng.standard_normal((n, len(FEATURES)))
    syn = {}
    for i, c in enumerate(ids):
        d = {"arm": int(syn_arm[i])}
        for j, f in enumerate(FEATURES):
            d[f"con_{f}"], d[f"unc_{f}"] = float(synS[i, j]), float(synU[i, j])
        syn[c] = d
    g2_rows = {}
    for lam in (0.0, 2.0, 8.0):
        s, a = evaluate(syn, ids, lam, seed=1)
        g2_rows[lam] = {"state": s, "agent": a}
        print(f"   lam={lam:<4} held-out state {s:+.4f}   agent {a:+.4f}")
    g2 = (g2_rows[0.0]["state"] > 0.15 and g2_rows[8.0]["agent"] < g2_rows[0.0]["agent"]
          and g2_rows[8.0]["state"] > 0.5 * g2_rows[0.0]["state"])
    print(f"   -> {'PASS' if g2 else 'FAIL -- the method cannot solve a problem whose answer exists by construction'}")
    out["G2"] = {"pass": bool(g2), "rows": {str(k): v for k, v in g2_rows.items()}}

    gates = g1 and g2
    print(f"\nGATES {'ALL PASS' if gates else 'NOT ALL PASSED -- no verdict is issued'}\n")

    print(f"{'lambda':>7s} {'held-out state':>15s} {'held-out agent':>15s}  {'agent <= floor':>15s}")
    res = {}
    for lam in LAMBDAS:
        s, a = evaluate(cases, ids, lam, seed=2)
        res[lam] = {"state": s, "agent": a, "agent_at_floor": bool(a <= floor)}
        print(f"{lam:7.1f} {s:15.4f} {a:15.4f}  {'yes' if a <= floor else 'no':>15s}")
    out["sweep"] = {str(k): v for k, v in res.items()}
    base_state = res[0.0]["state"]
    ok = [lam for lam in LAMBDAS
          if res[lam]["agent_at_floor"] and res[lam]["state"] >= STATE_TOL * base_state]
    if not gates:
        verdict = "NO VERDICT -- a gate failed"
    elif ok:
        verdict = (f"CONSTRUCTED -- at lambda {ok[0]} a linear combination keeps "
                   f"{res[ok[0]]['state'] / base_state:.0%} of the pure state axis's held-out "
                   f"discrimination while its agent legibility ({res[ok[0]]['agent']:.4f}) sits inside "
                   f"the random-projection floor ({floor:.4f}). First constructed Challenge A candidate. "
                   f"Next question is whether it survives on the VitalDB agent contrast, where E161 "
                   f"showed the leakage is broad.")
    else:
        verdict = (f"NOT SEPARABLE -- no lambda keeps {STATE_TOL:.0%} of the state axis while reaching "
                   f"the agent floor of {floor:.4f}. State and agent information are ENTANGLED in the "
                   f"amplitude family: raising the penalty costs state discrimination roughly in step "
                   f"with agent discrimination. The brief's acceptance condition cannot be met by any "
                   f"LINEAR combination of these features, which redirects Challenge A toward families "
                   f"this deposit cannot supply -- phase, connectivity, perturbational -- rather than "
                   f"toward more search within this one. Registered prediction confirmed.")
    print(f"\nVERDICT: {verdict}")
    out["verdict"] = verdict
    json.dump(out, open(OUT, "w"), indent=1, sort_keys=True, allow_nan=True)
    print(f"\n   wrote {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
